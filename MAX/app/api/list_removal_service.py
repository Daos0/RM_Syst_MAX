from __future__ import annotations

from datetime import datetime, timezone

from fastapi import HTTPException
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import ShoppingList, Space, SpaceMember, UserListPin


async def remove_list_for_member(
    session: AsyncSession,
    shopping_list: ShoppingList,
    member: SpaceMember,
) -> tuple[str, SpaceMember | None]:
    """Удаляет обычный список или выводит участника из совместной покупки."""
    if shopping_list.category != "shared":
        if member.role != "owner":
            raise HTTPException(
                status_code=403,
                detail="Только владелец может удалить список",
            )
        shopping_list.status = "archived"
        shopping_list.version += 1
        return "archived", None

    active_members = (
        await session.execute(
            select(SpaceMember)
            .where(
                SpaceMember.space_id == shopping_list.space_id,
                SpaceMember.left_at.is_(None),
            )
            .order_by(SpaceMember.joined_at, SpaceMember.id)
            .with_for_update()
        )
    ).scalars().all()
    remaining = [candidate for candidate in active_members if candidate.id != member.id]
    if not remaining:
        shopping_list.status = "archived"
        shopping_list.version += 1
        return "archived", None

    successor = None
    space = await session.get(Space, shopping_list.space_id)
    if space is None:
        raise HTTPException(status_code=404, detail="Пространство списка не найдено")
    if member.role == "owner" or space.owner_user_id == member.user_id:
        successor = remaining[0]
        successor.role = "owner"
        space.owner_user_id = successor.user_id

    member.left_at = datetime.now(timezone.utc)
    await session.execute(
        delete(UserListPin).where(
            UserListPin.user_id == member.user_id,
            UserListPin.list_id == shopping_list.id,
        )
    )
    return "left", successor
