from __future__ import annotations

from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Space, SpaceMember, User


async def space_for_new_list(
    session: AsyncSession,
    *,
    requested_space_id: UUID,
    category: str,
    title: str,
    user_id: UUID,
    current_member: SpaceMember,
) -> tuple[Space, SpaceMember]:
    target_space = await session.get(Space, requested_space_id)
    if target_space is None or target_space.kind != category:
        raise HTTPException(status_code=422, detail="Категория списка не совпадает с разделом")
    if category != "shared":
        return target_space, current_member

    user = await session.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=401, detail="Требуется вход")
    target_space = Space(kind="shared", title=title, owner_user_id=user.id)
    session.add(target_space)
    await session.flush()
    member = SpaceMember(space_id=target_space.id, user_id=user.id, role="owner")
    session.add(member)
    await session.flush()
    return target_space, member
