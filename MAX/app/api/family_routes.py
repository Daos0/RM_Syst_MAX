from __future__ import annotations

import os
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_current_user, get_session
from app.api.family_service import FamilyError, leave_family_group, remove_family_member
from app.api.invitation_service import InvitationError, create_family_invitation
from app.api.routes import current_member
from app.api.share_links import invitation_links
from app.db.models import Space, User


router = APIRouter(prefix="/api/v1/families", tags=["families"])


@router.post("/{space_id}/invitations", status_code=status.HTTP_201_CREATED)
async def invite_to_family(
    space_id: UUID,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> dict:
    async with session.begin():
        space = await session.get(Space, space_id)
        if space is None or space.archived_at is not None or space.kind != "family":
            raise HTTPException(status_code=404, detail="Семейная группа не найдена")
        member = await current_member(session, user.id, space_id=space_id)
        try:
            invitation, code = await create_family_invitation(session, space, member)
        except InvitationError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
    bot_urls, share_urls = invitation_links(
        code=code,
        message="Присоединяйтесь к моей семейной группе",
        max_username=os.getenv("MAX_BOT_USERNAME"),
        telegram_username=os.getenv("TELEGRAM_BOT_USERNAME"),
    )
    if not bot_urls:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Публичные имена ботов не настроены",
        )
    primary = "max" if "max" in bot_urls else next(iter(bot_urls))
    return {
        "code": code,
        "bot_url": bot_urls[primary],
        "share_url": share_urls[primary],
        "bot_urls": bot_urls,
        "share_urls": share_urls,
        "expires_at": invitation.expires_at.isoformat(),
        "space_id": str(space.id),
        "title": space.title,
    }


@router.delete("/{space_id}/members/{member_id}", status_code=status.HTTP_204_NO_CONTENT)
async def exclude_family_member(
    space_id: UUID,
    member_id: UUID,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> None:
    async with session.begin():
        space = await session.get(Space, space_id)
        if space is None or space.archived_at is not None:
            raise HTTPException(status_code=404, detail="Семейная группа не найдена")
        actor = await current_member(session, user.id, space_id=space_id)
        try:
            await remove_family_member(session, space, actor, member_id)
        except FamilyError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("/{space_id}/leave", status_code=status.HTTP_204_NO_CONTENT)
async def leave_family(
    space_id: UUID,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> None:
    async with session.begin():
        space = await session.get(Space, space_id)
        if space is None or space.archived_at is not None:
            raise HTTPException(status_code=404, detail="Семейная группа не найдена")
        member = await current_member(session, user.id, space_id=space_id)
        try:
            await leave_family_group(session, space, member)
        except FamilyError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
