from __future__ import annotations

import os
import secrets
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Response, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.admin_audience_service import (
    audience_page,
    audience_segment_counts,
    audience_stats,
    create_campaign,
    export_audience_csv,
    platform_totals,
    segment_count,
    validate_platform,
    validate_segment,
)
from app.api.dependencies import get_session


router = APIRouter(prefix="/internal/admin/audience", tags=["internal-admin"])


def require_admin_bridge(
    token: str | None = Header(default=None, alias="X-Admin-Token"),
) -> str:
    expected = os.getenv("ADMIN_BRIDGE_TOKEN", "").strip()
    if not expected:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="admin_bridge_not_configured",
        )
    if not token or not secrets.compare_digest(token, expected):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="invalid_admin_bridge_token",
        )
    return token


def clean_platform(value: str) -> str:
    try:
        return validate_platform(value)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


def clean_segment(value: str) -> str:
    try:
        return validate_segment(value)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


class BroadcastPayload(BaseModel):
    platform: str
    segment: str = "all"
    text: str = Field(min_length=1, max_length=3500)


@router.get("")
async def overview(
    platform: str = Query(default="max"),
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=20, ge=1, le=100),
    search: str = Query(default="", max_length=160),
    _: str = Depends(require_admin_bridge),
    session: AsyncSession = Depends(get_session),
) -> dict:
    selected = clean_platform(platform)
    return {
        "platform": selected,
        "platforms": await platform_totals(session),
        "stats": await audience_stats(session, selected),
        "segments": await audience_segment_counts(session, selected),
        "users": await audience_page(
            session,
            selected,
            page=page,
            limit=limit,
            search=search,
        ),
    }


@router.get("/export.csv")
async def export_csv(
    platform: str = Query(default="max"),
    search: str = Query(default="", max_length=160),
    _: str = Depends(require_admin_bridge),
    session: AsyncSession = Depends(get_session),
) -> Response:
    selected = clean_platform(platform)
    content = await export_audience_csv(session, selected, search=search)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    return Response(
        content=content,
        media_type="text/csv; charset=utf-8",
        headers={
            "Content-Disposition": (
                f'attachment; filename="bot-users-{selected}-{timestamp}.csv"'
            )
        },
    )


@router.post("/broadcast/preview")
async def preview_broadcast(
    payload: BroadcastPayload,
    _: str = Depends(require_admin_bridge),
    session: AsyncSession = Depends(get_session),
) -> dict:
    platform = clean_platform(payload.platform)
    segment = clean_segment(payload.segment)
    return {"recipients": await segment_count(session, platform, segment)}


@router.post("/broadcast", status_code=status.HTTP_201_CREATED)
async def queue_broadcast(
    payload: BroadcastPayload,
    actor: str | None = Header(default=None, alias="X-Admin-Actor"),
    _: str = Depends(require_admin_bridge),
    session: AsyncSession = Depends(get_session),
) -> dict:
    platform = clean_platform(payload.platform)
    segment = clean_segment(payload.segment)
    text = payload.text.strip()
    if not text:
        raise HTTPException(status_code=422, detail="broadcast_text_required")
    async with session.begin():
        campaign = await create_campaign(
            session,
            platform=platform,
            segment=segment,
            message_text=text,
            created_by=(actor or "rm-admin")[:160],
        )
        if campaign.total_count == 0:
            raise HTTPException(status_code=422, detail="broadcast_has_no_recipients")
    return {
        "campaign_id": str(campaign.id),
        "platform": campaign.provider,
        "recipients": campaign.total_count,
        "status": campaign.status,
    }
