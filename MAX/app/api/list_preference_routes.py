from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import delete
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_current_user, get_session
from app.api.routes import current_member
from app.db.models import User, UserListPin


router = APIRouter(prefix="/api/v1/lists", tags=["list-preferences"])


class ListPinRequest(BaseModel):
    pinned: bool


@router.put("/{list_id}/pin")
async def set_list_pin(
    list_id: UUID,
    payload: ListPinRequest,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> dict:
    async with session.begin():
        await current_member(session, user.id, list_id=list_id)
        if payload.pinned:
            await session.execute(
                insert(UserListPin)
                .values(user_id=user.id, list_id=list_id)
                .on_conflict_do_nothing(index_elements=["user_id", "list_id"])
            )
        else:
            await session.execute(
                delete(UserListPin).where(
                    UserListPin.user_id == user.id,
                    UserListPin.list_id == list_id,
                )
            )
    return {"list_id": str(list_id), "is_pinned": payload.pinned}
