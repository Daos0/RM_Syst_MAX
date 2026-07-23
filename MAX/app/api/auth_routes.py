from __future__ import annotations

import os
import secrets
from datetime import datetime, timedelta, timezone
from hashlib import sha256

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import SESSION_COOKIE, get_current_user, get_session
from app.platforms.max.auth import MaxInitDataError, validate_max_init_data
from app.api.schemas import MaxAuthRequest, TelegramAuthRequest
from app.db.models import (
    ColorPalette,
    Department,
    Product,
    ProductUserStat,
    Recipe,
    RecipeAddition,
    ShoppingItem,
    ShoppingList,
    Space,
    SpaceMember,
    User,
    UserCatalogItem,
    UserIdentity,
    UserListPin,
    UserSession,
)
from app.platforms.identity import PlatformIdentity, upsert_platform_user
from app.platforms.telegram.auth import (
    TelegramInitDataError,
    validate_telegram_init_data,
)

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])
SESSION_DAYS = 30


async def ensure_user_spaces(session: AsyncSession, user: User) -> list[tuple[Space, SpaceMember]]:
    existing = (
        await session.execute(
            select(Space, SpaceMember)
            .join(SpaceMember, SpaceMember.space_id == Space.id)
            .where(
                SpaceMember.user_id == user.id,
                SpaceMember.left_at.is_(None),
                Space.archived_at.is_(None),
            )
        )
    ).all()
    titles = {
        "personal": "Для себя",
        "family": "Для семьи",
        "shared": "Совместно",
    }
    by_kind = {}
    for space, member in existing:
        if space.kind == "personal" and space.owner_user_id == user.id:
            by_kind.setdefault(space.kind, (space, member))
        elif space.kind == "family":
            by_kind.setdefault(space.kind, (space, member))
        elif (
            space.kind == "shared"
            and space.owner_user_id == user.id
            and space.title == titles["shared"]
        ):
            by_kind.setdefault(space.kind, (space, member))
    color_id = await session.scalar(
        select(ColorPalette.id)
        .where(ColorPalette.is_active.is_(True))
        .order_by(ColorPalette.sort_order)
        .limit(1)
    )
    for kind, title in titles.items():
        if kind in by_kind:
            continue
        space = Space(kind=kind, title=title, owner_user_id=user.id)
        session.add(space)
        await session.flush()
        member = SpaceMember(
            space_id=space.id,
            user_id=user.id,
            role="owner",
            color_id=color_id if kind == "personal" else None,
        )
        session.add(member)
        await session.flush()
        by_kind[kind] = (space, member)
    return [by_kind[kind] for kind in titles]


async def cabinet_payload(session: AsyncSession, user: User) -> dict:
    await ensure_user_spaces(session, user)
    spaces = (
        await session.execute(
            select(Space, SpaceMember)
            .join(SpaceMember, SpaceMember.space_id == Space.id)
            .where(
                SpaceMember.user_id == user.id,
                SpaceMember.left_at.is_(None),
                Space.archived_at.is_(None),
            )
            .order_by(Space.kind, Space.created_at)
        )
    ).all()
    list_rows = (
        await session.execute(
            select(ShoppingList, func.count(ShoppingItem.id))
            .outerjoin(
                ShoppingItem,
                (ShoppingItem.list_id == ShoppingList.id)
                & ShoppingItem.deleted_at.is_(None),
            )
            .where(
                ShoppingList.space_id.in_([space.id for space, _ in spaces]),
                ShoppingList.status != "archived",
            )
            .group_by(ShoppingList.id)
            .order_by(ShoppingList.updated_at.desc())
        )
    ).all()
    family_members = (
        await session.execute(
            select(SpaceMember, User)
            .join(User, User.id == SpaceMember.user_id)
            .where(
                SpaceMember.space_id.in_(
                    [space.id for space, _ in spaces if space.kind == "family"]
                ),
                SpaceMember.left_at.is_(None),
            )
            .order_by(SpaceMember.joined_at, User.display_name)
        )
    ).all()
    members_by_space: dict[str, list[dict]] = {}
    for member, member_user in family_members:
        members_by_space.setdefault(str(member.space_id), []).append(
            {
                "id": str(member.id),
                "user_id": str(member_user.id),
                "display_name": member_user.display_name,
                "username": member_user.username,
                "avatar_url": member_user.avatar_url,
                "role": member.role,
                "is_current": member_user.id == user.id,
            }
        )
    lists_by_space: dict[str, list[dict]] = {}
    pinned_list_ids = set(
        (
            await session.scalars(
                select(UserListPin.list_id).where(UserListPin.user_id == user.id)
            )
        ).all()
    )
    purchased_count = 0
    for shopping_list, item_count in list_rows:
        lists_by_space.setdefault(str(shopping_list.space_id), []).append(
            {
                "id": str(shopping_list.id),
                "space_id": str(shopping_list.space_id),
                "title": shopping_list.title,
                "category": shopping_list.category,
                "status": shopping_list.status,
                "item_count": int(item_count or 0),
                "version": shopping_list.version,
                "is_pinned": shopping_list.id in pinned_list_ids,
            }
        )
    purchased_count = int(
        await session.scalar(
            select(func.count(ShoppingItem.id))
            .join(ShoppingList, ShoppingList.id == ShoppingItem.list_id)
            .where(
                ShoppingList.space_id.in_([space.id for space, _ in spaces]),
                ShoppingItem.status == "purchased",
                ShoppingItem.deleted_at.is_(None),
            )
        )
        or 0
    )
    personal_items = (
        await session.execute(
            select(UserCatalogItem, Department)
            .join(Department, Department.id == UserCatalogItem.department_id)
            .where(UserCatalogItem.user_id == user.id, UserCatalogItem.is_active.is_(True))
            .order_by(UserCatalogItem.updated_at.desc())
        )
    ).all()
    product_stats = (
        await session.execute(
            select(ProductUserStat, Product)
            .join(Product, Product.id == ProductUserStat.product_id)
            .where(ProductUserStat.user_id == user.id)
        )
    ).all()
    recipe_stats = (
        await session.execute(
            select(Recipe.id, Recipe.display_name, func.count(RecipeAddition.id))
            .join(RecipeAddition, RecipeAddition.recipe_id == Recipe.id)
            .join(SpaceMember, SpaceMember.id == RecipeAddition.created_by_member_id)
            .where(SpaceMember.user_id == user.id)
            .group_by(Recipe.id)
        )
    ).all()
    identities = (
        await session.scalars(
            select(UserIdentity)
            .where(UserIdentity.user_id == user.id)
            .order_by(UserIdentity.provider)
        )
    ).all()
    return {
        "user": {
            "id": str(user.id),
            "max_user_id": user.max_user_id,
            "display_name": user.display_name,
            "username": user.username,
            "avatar_url": user.avatar_url,
            "locale": user.locale,
            "platforms": [identity.provider for identity in identities],
        },
        "spaces": [
            {
                "id": str(space.id),
                "title": space.title,
                "kind": space.kind,
                "member_id": str(member.id),
                "role": member.role,
                "is_owner": space.owner_user_id == user.id,
                "members": members_by_space.get(str(space.id), []),
                "lists": lists_by_space.get(str(space.id), []),
            }
            for space, member in spaces
        ],
        "personal_catalog": [
            {
                "id": str(item.id),
                "name": item.display_name,
                "department_id": item.department_id,
                "category": department.name,
                "quantity": str(item.default_quantity),
                "unit": item.default_unit,
                "icon": item.icon,
            }
            for item, department in personal_items
        ],
        "signals": {
            "product_usage": {
                product.display_name.casefold(): {
                    "name": product.display_name,
                    "count": stat.purchase_count,
                    "added": stat.add_count,
                }
                for stat, product in product_stats
            },
            "recipe_usage": {
                str(recipe_id): {"name": recipe_name, "count": int(count)}
                for recipe_id, recipe_name, count in recipe_stats
            },
        },
        "stats": {
            "lists": len(list_rows),
            "personal_products": len(personal_items),
            "purchased": purchased_count,
        },
    }


@router.post("/max")
async def authenticate_max(
    payload: MaxAuthRequest,
    response: Response,
    request: Request,
    session: AsyncSession = Depends(get_session),
) -> dict:
    try:
        identity = validate_max_init_data(
            payload.init_data,
            os.getenv("MAX_BOT_TOKEN", ""),
            max_age_seconds=int(os.getenv("MAX_INIT_DATA_MAX_AGE", "3600")),
        )
    except MaxInitDataError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc)) from exc
    platform_identity = PlatformIdentity(
        provider="max",
        user_id=identity.user_id,
        display_name=identity.display_name,
        username=identity.username,
        avatar_url=identity.avatar_url,
        locale=identity.locale,
    )
    return await _authenticate_platform(
        platform_identity, response, request, session
    )


@router.post("/telegram")
async def authenticate_telegram(
    payload: TelegramAuthRequest,
    response: Response,
    request: Request,
    session: AsyncSession = Depends(get_session),
) -> dict:
    try:
        identity = validate_telegram_init_data(
            payload.init_data,
            os.getenv("TELEGRAM_BOT_TOKEN", ""),
            max_age_seconds=int(os.getenv("TELEGRAM_INIT_DATA_MAX_AGE", "3600")),
        )
    except TelegramInitDataError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc)
        ) from exc
    return await _authenticate_platform(identity, response, request, session)


async def _authenticate_platform(
    identity: PlatformIdentity,
    response: Response,
    request: Request,
    session: AsyncSession,
) -> dict:
    async with session.begin():
        user = await upsert_platform_user(session, identity)
        await ensure_user_spaces(session, user)
        raw_token = secrets.token_urlsafe(48)
        expires_at = datetime.now(timezone.utc) + timedelta(days=SESSION_DAYS)
        session.add(
            UserSession(
                user_id=user.id,
                token_hash=sha256(raw_token.encode()).hexdigest(),
                expires_at=expires_at,
            )
        )
    response.set_cookie(
        SESSION_COOKIE,
        raw_token,
        max_age=SESSION_DAYS * 86400,
        expires=expires_at,
        httponly=True,
        secure=(
            request.url.scheme == "https"
            or request.headers.get("x-forwarded-proto", "")
            .split(",", 1)[0]
            .strip()
            == "https"
            or os.getenv("MAX_SECURE_COOKIES") == "1"
        ),
        samesite="lax",
        path="/",
    )
    return {
        **(await cabinet_payload(session, user)),
        "active_platform": identity.provider,
        "session_token": raw_token,
    }


@router.get("/session")
async def current_session(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> dict:
    return await cabinet_payload(session, user)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(
    response: Response,
    request: Request,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> None:
    token = request.cookies.get(SESSION_COOKIE)
    if token:
        auth_session = await session.scalar(
            select(UserSession).where(
                UserSession.user_id == user.id,
                UserSession.token_hash == sha256(token.encode()).hexdigest(),
            )
        )
        if auth_session:
            auth_session.revoked_at = datetime.now(timezone.utc)
            await session.commit()
    response.delete_cookie(SESSION_COOKIE, path="/")
