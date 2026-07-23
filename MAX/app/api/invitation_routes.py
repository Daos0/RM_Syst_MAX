from __future__ import annotations

import os
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_current_user, get_session
from app.api.invitation_service import InvitationError, accept_invitation, create_invitation
from app.api.routes import current_member
from app.api.share_links import invitation_links
from app.db.models import ShoppingList, User


router = APIRouter(prefix="/api/v1", tags=["invitations"])


@router.post("/lists/{list_id}/invitations", status_code=status.HTTP_201_CREATED)
async def invite_to_list(
    list_id: UUID,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> dict:
    async with session.begin():
        shopping_list = await session.get(ShoppingList, list_id)
        if shopping_list is None or shopping_list.status == "archived":
            raise HTTPException(status_code=404, detail="Список не найден")
        member = await current_member(session, user.id, list_id=list_id)
        try:
            invitation, code = await create_invitation(session, shopping_list, member)
        except InvitationError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

    bot_urls, share_urls = invitation_links(
        code=code,
        message=f"Присоединяйтесь к покупке «{shopping_list.title}»",
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
        "list_id": str(shopping_list.id),
        "title": shopping_list.title,
    }


@router.post("/invitations/{code}/accept")
async def join_by_code(
    code: str,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> dict:
    async with session.begin():
        try:
            return await accept_invitation(session, code, user)
        except InvitationError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
