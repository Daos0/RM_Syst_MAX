from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator
from uuid import UUID

from fastapi import APIRouter, Cookie, Header, HTTPException, Request, status
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import SESSION_COOKIE, get_optional_current_user
from app.db.models import ShoppingList, SpaceMember
from app.db.session import Database


router = APIRouter(prefix="/api/v1", tags=["realtime"])
REALTIME_INTERVAL_SECONDS = 0.8
HEARTBEAT_INTERVAL_SECONDS = 16


async def visible_list_version(
    session: AsyncSession,
    user_id: UUID,
    list_id: UUID,
) -> int | None:
    return await session.scalar(
        select(ShoppingList.version)
        .join(SpaceMember, SpaceMember.space_id == ShoppingList.space_id)
        .where(
            ShoppingList.id == list_id,
            ShoppingList.status != "archived",
            SpaceMember.user_id == user_id,
            SpaceMember.left_at.is_(None),
        )
    )


def event_message(event: str, payload: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(payload, separators=(',', ':'))}\n\n"


async def list_event_stream(
    request: Request,
    database: Database,
    user_id: UUID,
    list_id: UUID,
    initial_version: int,
) -> AsyncIterator[str]:
    current_version = initial_version
    elapsed = 0.0
    yield event_message("ready", {"version": current_version})
    while not await request.is_disconnected():
        await asyncio.sleep(REALTIME_INTERVAL_SECONDS)
        elapsed += REALTIME_INTERVAL_SECONDS
        async with database.sessions() as session:
            version = await visible_list_version(session, user_id, list_id)
        if version is None:
            yield event_message("access_revoked", {})
            return
        if version != current_version:
            current_version = version
            elapsed = 0.0
            yield event_message("list_changed", {"version": current_version})
        elif elapsed >= HEARTBEAT_INTERVAL_SECONDS:
            elapsed = 0.0
            yield ": keep-alive\n\n"


@router.get("/lists/{list_id}/events")
async def list_events(
    list_id: UUID,
    request: Request,
    session_token: str | None = Cookie(default=None, alias=SESSION_COOKIE),
    authorization: str | None = Header(default=None),
) -> StreamingResponse:
    database: Database | None = getattr(request.app.state, "database", None)
    if database is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="База данных не подключена",
        )
    async with database.sessions() as session:
        user = await get_optional_current_user(session_token, authorization, session)
        if user is None:
            raise HTTPException(
                status_code=401,
                detail="Требуется вход через MAX или Telegram",
            )
        initial_version = await visible_list_version(session, user.id, list_id)
    if initial_version is None:
        raise HTTPException(status_code=403, detail="Нет доступа к этому списку")
    return StreamingResponse(
        list_event_stream(request, database, user.id, list_id, initial_version),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-transform",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
