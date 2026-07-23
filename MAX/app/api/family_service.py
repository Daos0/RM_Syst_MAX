from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import (
    RecipeAddition,
    SectionAssignment,
    ShoppingEvent,
    ShoppingItem,
    ShoppingList,
    Space,
    SpaceMember,
    User,
)


class FamilyError(ValueError):
    pass


async def _active_family_memberships(
    session: AsyncSession, user_id: UUID
) -> list[tuple[Space, SpaceMember]]:
    return list(
        (
            await session.execute(
                select(Space, SpaceMember)
                .join(SpaceMember, SpaceMember.space_id == Space.id)
                .where(
                    Space.kind == "family",
                    Space.archived_at.is_(None),
                    SpaceMember.user_id == user_id,
                    SpaceMember.left_at.is_(None),
                )
            )
        ).all()
    )


async def _move_solo_family_lists_to_personal(
    session: AsyncSession,
    user: User,
    family_space: Space,
    family_member: SpaceMember,
) -> None:
    personal = (
        await session.execute(
            select(Space, SpaceMember)
            .join(SpaceMember, SpaceMember.space_id == Space.id)
            .where(
                Space.kind == "personal",
                Space.owner_user_id == user.id,
                Space.archived_at.is_(None),
                SpaceMember.user_id == user.id,
                SpaceMember.left_at.is_(None),
            )
        )
    ).one_or_none()
    if personal is None:
        raise FamilyError("Личное пространство пользователя не найдено")
    personal_space, personal_member = personal
    list_ids = list(
        (
            await session.scalars(
                select(ShoppingList.id).where(
                    ShoppingList.space_id == family_space.id,
                    ShoppingList.status != "archived",
                )
            )
        ).all()
    )
    if list_ids:
        await session.execute(
            update(ShoppingList)
            .where(ShoppingList.id.in_(list_ids))
            .values(
                space_id=personal_space.id,
                category="personal",
                created_by_member_id=personal_member.id,
            )
        )
        await session.execute(
            update(ShoppingItem)
            .where(
                ShoppingItem.list_id.in_(list_ids),
                ShoppingItem.created_by_member_id == family_member.id,
            )
            .values(created_by_member_id=personal_member.id)
        )
        await session.execute(
            update(ShoppingItem)
            .where(
                ShoppingItem.list_id.in_(list_ids),
                ShoppingItem.assigned_member_id == family_member.id,
            )
            .values(assigned_member_id=None, status="active")
        )
        await session.execute(
            update(ShoppingItem)
            .where(
                ShoppingItem.list_id.in_(list_ids),
                ShoppingItem.purchased_by_member_id == family_member.id,
            )
            .values(purchased_by_member_id=personal_member.id)
        )
        await session.execute(
            update(SectionAssignment)
            .where(
                SectionAssignment.list_id.in_(list_ids),
                SectionAssignment.member_id == family_member.id,
            )
            .values(member_id=personal_member.id)
        )
        await session.execute(
            update(ShoppingEvent)
            .where(
                ShoppingEvent.list_id.in_(list_ids),
                ShoppingEvent.actor_member_id == family_member.id,
            )
            .values(actor_member_id=personal_member.id)
        )
        await session.execute(
            update(RecipeAddition)
            .where(
                RecipeAddition.list_id.in_(list_ids),
                RecipeAddition.created_by_member_id == family_member.id,
            )
            .values(created_by_member_id=personal_member.id)
        )
    now = datetime.now(timezone.utc)
    family_member.left_at = now
    family_member.color_id = None
    family_space.archived_at = now


async def prepare_family_join(
    session: AsyncSession, user: User, target_space: Space
) -> SpaceMember | None:
    memberships = await _active_family_memberships(session, user.id)
    for space, member in memberships:
        if space.id == target_space.id:
            return member
    if len(memberships) > 1:
        raise FamilyError("Обнаружено несколько семейных групп — обратитесь в поддержку")
    if memberships:
        current_space, current_member = memberships[0]
        active_count = int(
            await session.scalar(
                select(func.count(SpaceMember.id)).where(
                    SpaceMember.space_id == current_space.id,
                    SpaceMember.left_at.is_(None),
                )
            )
            or 0
        )
        if current_space.owner_user_id != user.id or active_count > 1:
            raise FamilyError("Сначала выйдите из текущей семейной группы")
        await _move_solo_family_lists_to_personal(
            session, user, current_space, current_member
        )
    return None


async def remove_family_member(
    session: AsyncSession,
    space: Space,
    actor: SpaceMember,
    member_id: UUID,
) -> SpaceMember:
    if space.kind != "family" or actor.role != "owner":
        raise FamilyError("Управлять участниками может только владелец семьи")
    member = await session.scalar(
        select(SpaceMember).where(
            SpaceMember.id == member_id,
            SpaceMember.space_id == space.id,
            SpaceMember.left_at.is_(None),
        )
    )
    if member is None:
        raise FamilyError("Участник не найден")
    if member.role == "owner":
        raise FamilyError("Владельца семьи нельзя исключить")
    list_ids = select(ShoppingList.id).where(ShoppingList.space_id == space.id)
    await session.execute(
        update(ShoppingItem)
        .where(
            ShoppingItem.list_id.in_(list_ids),
            ShoppingItem.assigned_member_id == member.id,
        )
        .values(assigned_member_id=None, status="active")
    )
    await session.execute(
        delete(SectionAssignment).where(
            SectionAssignment.list_id.in_(list_ids),
            SectionAssignment.member_id == member.id,
        )
    )
    member.left_at = datetime.now(timezone.utc)
    member.color_id = None
    return member


async def leave_family_group(
    session: AsyncSession, space: Space, member: SpaceMember
) -> None:
    if space.kind != "family":
        raise FamilyError("Семейная группа не найдена")
    if member.role == "owner":
        raise FamilyError("Владелец не может выйти: сначала исключите участников")
    await remove_family_member(
        session,
        space,
        await session.scalar(
            select(SpaceMember).where(
                SpaceMember.space_id == space.id,
                SpaceMember.role == "owner",
                SpaceMember.left_at.is_(None),
            )
        ),
        member.id,
    )
