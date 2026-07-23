from __future__ import annotations

import secrets
from datetime import datetime, timedelta, timezone
from hashlib import sha256

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.family_service import FamilyError, prepare_family_join
from app.db.models import (
    ColorPalette,
    Invitation,
    RecipeAddition,
    SectionAssignment,
    ShoppingEvent,
    ShoppingItem,
    ShoppingList,
    Space,
    SpaceMember,
    User,
)


INVITE_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
INVITE_CODE_LENGTH = 8
INVITE_LIFETIME = timedelta(days=7)
INVITE_MAX_USES = 50


class InvitationError(ValueError):
    pass


def normalize_invite_code(value: str) -> str:
    code = value.strip().upper()
    if code.startswith("JOIN_") or code.startswith("JOIN-"):
        code = code[5:]
    if len(code) != INVITE_CODE_LENGTH or any(char not in INVITE_ALPHABET for char in code):
        raise InvitationError("Проверьте код приглашения")
    return code


def invite_hash(code: str) -> str:
    return sha256(normalize_invite_code(code).encode()).hexdigest()


async def create_invitation(
    session: AsyncSession,
    shopping_list: ShoppingList,
    member: SpaceMember,
) -> tuple[Invitation, str]:
    if shopping_list.category != "shared":
        raise InvitationError("Поделиться можно только совместным списком")
    if member.role != "owner":
        raise InvitationError("Создать приглашение может владелец списка")

    member = await isolate_shared_list_space(session, shopping_list, member)

    return await _issue_invitation(session, shopping_list.space_id, member)


async def create_family_invitation(
    session: AsyncSession,
    space: Space,
    member: SpaceMember,
) -> tuple[Invitation, str]:
    if space.kind != "family":
        raise InvitationError("Семейная группа не найдена")
    if member.role != "owner":
        raise InvitationError("Приглашать в семью может только владелец")
    return await _issue_invitation(session, space.id, member)


async def _issue_invitation(
    session: AsyncSession,
    space_id,
    member: SpaceMember,
) -> tuple[Invitation, str]:
    now = datetime.now(timezone.utc)
    existing = (
        await session.execute(
            select(Invitation).where(
                Invitation.space_id == space_id,
                Invitation.revoked_at.is_(None),
            )
        )
    ).scalars().all()
    for invitation in existing:
        invitation.revoked_at = now

    for _ in range(10):
        code = "".join(secrets.choice(INVITE_ALPHABET) for _ in range(INVITE_CODE_LENGTH))
        token_hash = sha256(code.encode()).hexdigest()
        duplicate = await session.scalar(
            select(Invitation.id).where(Invitation.token_hash == token_hash)
        )
        if duplicate is None:
            break
    else:
        raise RuntimeError("Не удалось создать уникальный код приглашения")

    invitation = Invitation(
        space_id=space_id,
        created_by_member_id=member.id,
        token_hash=token_hash,
        role="editor",
        max_uses=INVITE_MAX_USES,
        expires_at=now + INVITE_LIFETIME,
    )
    session.add(invitation)
    await session.flush()
    return invitation, code


async def isolate_shared_list_space(
    session: AsyncSession,
    shopping_list: ShoppingList,
    current: SpaceMember,
) -> SpaceMember:
    """Делает выбранный совместный список отдельной границей доступа."""
    other_list_id = await session.scalar(
        select(ShoppingList.id)
        .where(
            ShoppingList.space_id == shopping_list.space_id,
            ShoppingList.id != shopping_list.id,
        )
        .limit(1)
    )
    if other_list_id is None:
        return current

    old_space = await session.get(Space, shopping_list.space_id)
    if old_space is None:
        raise InvitationError("Пространство совместной покупки не найдено")
    old_members = (
        await session.execute(
            select(SpaceMember).where(
                SpaceMember.space_id == old_space.id,
                SpaceMember.left_at.is_(None),
            )
        )
    ).scalars().all()
    new_space = Space(
        kind="shared",
        title=shopping_list.title,
        owner_user_id=old_space.owner_user_id,
    )
    session.add(new_space)
    await session.flush()

    member_map: dict = {}
    for old_member in old_members:
        new_member = SpaceMember(
            space_id=new_space.id,
            user_id=old_member.user_id,
            role=old_member.role,
            color_id=old_member.color_id,
        )
        session.add(new_member)
        await session.flush()
        member_map[old_member.id] = new_member

    replacement = member_map.get(current.id)
    if replacement is None:
        raise InvitationError("Владелец списка не найден")
    shopping_list.space_id = new_space.id
    shopping_list.created_by_member_id = member_map.get(
        shopping_list.created_by_member_id, replacement
    ).id

    items = (
        await session.execute(
            select(ShoppingItem).where(ShoppingItem.list_id == shopping_list.id)
        )
    ).scalars().all()
    for item in items:
        item.created_by_member_id = member_map.get(item.created_by_member_id, replacement).id
        if item.assigned_member_id in member_map:
            item.assigned_member_id = member_map[item.assigned_member_id].id
        if item.purchased_by_member_id in member_map:
            item.purchased_by_member_id = member_map[item.purchased_by_member_id].id

    assignments = (
        await session.execute(
            select(SectionAssignment).where(SectionAssignment.list_id == shopping_list.id)
        )
    ).scalars().all()
    for assignment in assignments:
        if assignment.member_id in member_map:
            assignment.member_id = member_map[assignment.member_id].id

    events = (
        await session.execute(
            select(ShoppingEvent).where(ShoppingEvent.list_id == shopping_list.id)
        )
    ).scalars().all()
    for event in events:
        event.actor_member_id = member_map.get(event.actor_member_id, replacement).id

    additions = (
        await session.execute(
            select(RecipeAddition).where(RecipeAddition.list_id == shopping_list.id)
        )
    ).scalars().all()
    for addition in additions:
        addition.created_by_member_id = member_map.get(
            addition.created_by_member_id, replacement
        ).id

    await session.flush()
    return replacement


async def _free_color_id(session: AsyncSession, space_id) -> int | None:
    used = select(SpaceMember.color_id).where(
        SpaceMember.space_id == space_id,
        SpaceMember.left_at.is_(None),
        SpaceMember.color_id.is_not(None),
    )
    return await session.scalar(
        select(ColorPalette.id)
        .where(ColorPalette.is_active.is_(True), ColorPalette.id.not_in(used))
        .order_by(ColorPalette.sort_order)
        .limit(1)
    )


async def accept_invitation(
    session: AsyncSession,
    code: str,
    user: User,
) -> dict:
    normalized = normalize_invite_code(code)
    now = datetime.now(timezone.utc)
    invitation = await session.scalar(
        select(Invitation)
        .where(Invitation.token_hash == sha256(normalized.encode()).hexdigest())
        .with_for_update()
    )
    if invitation is None:
        raise InvitationError("Приглашение не найдено")
    if invitation.revoked_at is not None or invitation.expires_at <= now:
        raise InvitationError("Срок действия приглашения истёк")
    if invitation.use_count >= invitation.max_uses:
        raise InvitationError("Лимит участников по этой ссылке исчерпан")

    space = await session.get(Space, invitation.space_id)
    if space is None or space.archived_at is not None or space.kind not in {"shared", "family"}:
        raise InvitationError("Приглашение больше недоступно")
    if space.kind == "family":
        try:
            existing_member = await prepare_family_join(session, user, space)
        except FamilyError as exc:
            raise InvitationError(str(exc)) from exc
        joined = existing_member is None
        member = existing_member or await session.scalar(
            select(SpaceMember).where(
                SpaceMember.space_id == space.id,
                SpaceMember.user_id == user.id,
            )
        )
        if member is None:
            member = SpaceMember(
                space_id=space.id,
                user_id=user.id,
                role=invitation.role,
                color_id=await _free_color_id(session, space.id),
            )
            session.add(member)
        elif member.left_at is not None:
            member.left_at = None
            member.role = invitation.role
            member.color_id = await _free_color_id(session, space.id)
        if joined:
            invitation.use_count += 1
        first_list = await session.scalar(
            select(ShoppingList)
            .where(
                ShoppingList.space_id == space.id,
                ShoppingList.status != "archived",
            )
            .order_by(ShoppingList.created_at)
            .limit(1)
        )
        await session.flush()
        return {
            "joined": joined,
            "kind": "family",
            "list_id": str(first_list.id) if first_list else "",
            "title": space.title,
            "category": "family",
            "space_id": str(space.id),
        }
    shopping_list = await session.scalar(
        select(ShoppingList)
        .where(
            ShoppingList.space_id == space.id,
            ShoppingList.status != "archived",
        )
        .order_by(ShoppingList.created_at)
        .limit(1)
    )
    if shopping_list is None:
        raise InvitationError("Совместная покупка больше недоступна")

    member = await session.scalar(
        select(SpaceMember).where(
            SpaceMember.space_id == space.id,
            SpaceMember.user_id == user.id,
        )
    )
    joined = member is None or member.left_at is not None
    if member is None:
        member = SpaceMember(
            space_id=space.id,
            user_id=user.id,
            role=invitation.role,
            color_id=await _free_color_id(session, space.id),
        )
        session.add(member)
    elif member.left_at is not None:
        member.left_at = None
        member.role = invitation.role
        member.color_id = await _free_color_id(session, space.id)

    if joined:
        invitation.use_count += 1
    await session.flush()
    return {
        "joined": joined,
        "kind": "shared",
        "list_id": str(shopping_list.id),
        "title": shopping_list.title,
        "category": shopping_list.category,
        "space_id": str(space.id),
    }
