from __future__ import annotations

from collections.abc import AsyncIterator

from datetime import datetime, timezone
from hashlib import sha256
from uuid import UUID

from fastapi import Cookie, Depends, Header, HTTPException, Request, status
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import User, UserSession
from app.db.session import Database

SESSION_COOKIE = "max_session"


async def get_session(request: Request) -> AsyncIterator[AsyncSession]:
    database: Database | None = getattr(request.app.state, "database", None)
    if database is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="База данных не подключена",
        )
    async with database.sessions() as session:
        yield session


async def get_current_user(
    session_token: str | None = Cookie(default=None, alias=SESSION_COOKIE),
    authorization: str | None = Header(default=None),
    session: AsyncSession = Depends(get_session),
) -> User:
    user = await get_optional_current_user(session_token, authorization, session)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Требуется вход через MAX или Telegram",
        )
    return user


async def get_optional_current_user(
    session_token: str | None = Cookie(default=None, alias=SESSION_COOKIE),
    authorization: str | None = Header(default=None),
    session: AsyncSession = Depends(get_session),
) -> User | None:
    if authorization and authorization.startswith("Bearer "):
        session_token = authorization.removeprefix("Bearer ").strip()
    if not session_token:
        return None
    token_hash = sha256(session_token.encode()).hexdigest()
    now = datetime.now(timezone.utc)
    row = await session.execute(
        select(UserSession, User)
        .join(User, User.id == UserSession.user_id)
        .where(
            UserSession.token_hash == token_hash,
            UserSession.revoked_at.is_(None),
            UserSession.expires_at > now,
        )
    )
    auth_session, user = row.one_or_none() or (None, None)
    if auth_session is None or user is None:
        return None
    await session.execute(
        update(UserSession)
        .where(UserSession.id == auth_session.id)
        .values(last_seen_at=now)
    )
    await session.commit()
    return user


async def get_max_user_id(user: User = Depends(get_current_user)) -> str:
    if user.max_user_id is None:
        raise HTTPException(status_code=409, detail="Аккаунт MAX не подключён")
    return user.max_user_id


async def get_optional_max_user_id(
    user: User | None = Depends(get_optional_current_user),
) -> str | None:
    return user.max_user_id if user else None


async def get_user_id(user: User = Depends(get_current_user)) -> UUID:
    return user.id


async def get_optional_user_id(
    user: User | None = Depends(get_optional_current_user),
) -> UUID | None:
    return user.id if user else None
