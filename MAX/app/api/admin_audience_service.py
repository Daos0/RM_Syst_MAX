from __future__ import annotations

import csv
import io
from datetime import datetime, timedelta, timezone
from math import ceil

from sqlalchemy import func, insert, literal, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import BroadcastCampaign, BroadcastRecipient, UserIdentity


PLATFORMS = {"max", "telegram"}
SEGMENTS = {"all", "active_7d", "new_7d", "inactive_30d"}


def validate_platform(value: str) -> str:
    platform = value.strip().lower()
    if platform not in PLATFORMS:
        raise ValueError("unknown_platform")
    return platform


def validate_segment(value: str) -> str:
    segment = value.strip().lower()
    if segment not in SEGMENTS:
        raise ValueError("unknown_segment")
    return segment


def audience_query(
    platform: str,
    *,
    segment: str = "all",
    search: str = "",
):
    now = datetime.now(timezone.utc)
    query = select(UserIdentity).where(UserIdentity.provider == platform)
    if segment == "active_7d":
        query = query.where(UserIdentity.last_seen_at >= now - timedelta(days=7))
    elif segment == "new_7d":
        query = query.where(UserIdentity.created_at >= now - timedelta(days=7))
    elif segment == "inactive_30d":
        query = query.where(UserIdentity.last_seen_at < now - timedelta(days=30))
    term = search.strip()
    if term:
        pattern = f"%{term}%"
        query = query.where(
            or_(
                UserIdentity.display_name.ilike(pattern),
                UserIdentity.username.ilike(pattern),
                UserIdentity.provider_user_id.ilike(pattern),
            )
        )
    return query


async def platform_totals(session: AsyncSession) -> dict[str, dict[str, int]]:
    rows = (
        await session.execute(
            select(UserIdentity.provider, func.count(UserIdentity.id))
            .group_by(UserIdentity.provider)
        )
    ).all()
    totals = {provider: 0 for provider in sorted(PLATFORMS)}
    totals.update({str(provider): int(total) for provider, total in rows})
    return {provider: {"total": total} for provider, total in totals.items()}


async def audience_stats(session: AsyncSession, platform: str) -> dict[str, int]:
    now = datetime.now(timezone.utc)
    base = UserIdentity.provider == platform

    async def count(*conditions) -> int:
        value = await session.scalar(
            select(func.count(UserIdentity.id)).where(base, *conditions)
        )
        return int(value or 0)

    total = await count()
    return {
        "total": total,
        "new_24h": await count(UserIdentity.created_at >= now - timedelta(hours=24)),
        "active_7d": await count(UserIdentity.last_seen_at >= now - timedelta(days=7)),
        "reachable": total,
    }


async def audience_segment_counts(
    session: AsyncSession,
    platform: str,
) -> dict[str, int]:
    return {
        segment: await segment_count(session, platform, segment)
        for segment in ("all", "active_7d", "new_7d", "inactive_30d")
    }


def identity_json(identity: UserIdentity) -> dict:
    return {
        "id": str(identity.id),
        "provider": identity.provider,
        "provider_user_id": identity.provider_user_id,
        "username": identity.username,
        "display_name": identity.display_name,
        "locale": identity.locale,
        "created_at": identity.created_at.isoformat(),
        "last_seen_at": identity.last_seen_at.isoformat(),
    }


async def audience_page(
    session: AsyncSession,
    platform: str,
    *,
    page: int,
    limit: int,
    search: str,
) -> dict:
    safe_page = max(1, page)
    safe_limit = max(1, min(100, limit))
    query = audience_query(platform, search=search)
    total = int(
        await session.scalar(
            select(func.count()).select_from(query.subquery())
        )
        or 0
    )
    identities = (
        await session.execute(
            query.order_by(UserIdentity.created_at.desc())
            .offset((safe_page - 1) * safe_limit)
            .limit(safe_limit)
        )
    ).scalars().all()
    return {
        "items": [identity_json(identity) for identity in identities],
        "page": safe_page,
        "limit": safe_limit,
        "total": total,
        "pages": max(1, ceil(total / safe_limit)),
    }


async def export_audience_csv(
    session: AsyncSession,
    platform: str,
    *,
    search: str = "",
) -> bytes:
    identities = (
        await session.execute(
            audience_query(platform, search=search).order_by(
                UserIdentity.created_at.desc()
            )
        )
    ).scalars().all()
    output = io.StringIO(newline="")
    writer = csv.writer(output)
    writer.writerow(
        [
            "platform",
            "provider_user_id",
            "username",
            "display_name",
            "locale",
            "created_at",
            "last_seen_at",
        ]
    )
    for identity in identities:
        writer.writerow(
            [
                identity.provider,
                identity.provider_user_id,
                identity.username or "",
                identity.display_name,
                identity.locale,
                identity.created_at.isoformat(),
                identity.last_seen_at.isoformat(),
            ]
        )
    return ("\ufeff" + output.getvalue()).encode("utf-8")


async def segment_count(
    session: AsyncSession,
    platform: str,
    segment: str,
) -> int:
    query = audience_query(platform, segment=segment)
    return int(
        await session.scalar(select(func.count()).select_from(query.subquery())) or 0
    )


async def create_campaign(
    session: AsyncSession,
    *,
    platform: str,
    segment: str,
    message_text: str,
    created_by: str | None,
) -> BroadcastCampaign:
    campaign = BroadcastCampaign(
        provider=platform,
        segment=segment,
        message_text=message_text,
        created_by=created_by,
        status="queued",
    )
    session.add(campaign)
    await session.flush()

    source = audience_query(platform, segment=segment).with_only_columns(
        literal(campaign.id),
        UserIdentity.id,
        UserIdentity.provider_user_id,
        literal("queued"),
        literal(0),
    )
    await session.execute(
        insert(BroadcastRecipient).from_select(
            [
                "campaign_id",
                "identity_id",
                "provider_user_id",
                "status",
                "attempts",
            ],
            source,
        )
    )
    campaign.total_count = await segment_count(session, platform, segment)
    await session.flush()
    return campaign
