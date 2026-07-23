from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import User, UserIdentity


@dataclass(frozen=True, slots=True)
class PlatformIdentity:
    provider: str
    user_id: str
    display_name: str
    username: str | None = None
    avatar_url: str | None = None
    locale: str = "ru"


async def upsert_platform_user(
    session: AsyncSession,
    identity: PlatformIdentity,
) -> User:
    """Resolve one internal user for a verified messenger identity."""
    lock_key = f"shopping-identity:{identity.provider}:{identity.user_id}"
    await session.execute(select(func.pg_advisory_xact_lock(func.hashtext(lock_key))))

    row = await session.execute(
        select(UserIdentity, User)
        .join(User, User.id == UserIdentity.user_id)
        .where(
            UserIdentity.provider == identity.provider,
            UserIdentity.provider_user_id == identity.user_id,
        )
    )
    platform_identity, user = row.one_or_none() or (None, None)

    if user is None and identity.provider == "max":
        user = await session.scalar(
            select(User).where(User.max_user_id == identity.user_id)
        )

    if user is None:
        user = User(
            max_user_id=identity.user_id if identity.provider == "max" else None,
            display_name=identity.display_name,
            username=identity.username,
            avatar_url=identity.avatar_url,
            locale=identity.locale,
        )
        session.add(user)
        await session.flush()

    user.display_name = identity.display_name
    user.username = identity.username
    user.avatar_url = identity.avatar_url
    user.locale = identity.locale
    if identity.provider == "max":
        user.max_user_id = identity.user_id

    now = datetime.now(timezone.utc)
    if platform_identity is None:
        platform_identity = UserIdentity(
            user_id=user.id,
            provider=identity.provider,
            provider_user_id=identity.user_id,
            username=identity.username,
            display_name=identity.display_name,
            avatar_url=identity.avatar_url,
            locale=identity.locale,
            last_seen_at=now,
        )
        session.add(platform_identity)
    else:
        platform_identity.username = identity.username
        platform_identity.display_name = identity.display_name
        platform_identity.avatar_url = identity.avatar_url
        platform_identity.locale = identity.locale
        platform_identity.last_seen_at = now
    await session.flush()
    return user


async def platform_user(
    session: AsyncSession,
    provider: str,
    provider_user_id: str | int,
) -> User | None:
    user = await session.scalar(
        select(User)
        .join(UserIdentity, UserIdentity.user_id == User.id)
        .where(
            UserIdentity.provider == provider,
            UserIdentity.provider_user_id == str(provider_user_id),
        )
    )
    if user is None and provider == "max":
        user = await session.scalar(
            select(User).where(User.max_user_id == str(provider_user_id))
        )
    return user
