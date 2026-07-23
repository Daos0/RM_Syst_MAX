from __future__ import annotations

from app.api.auth_routes import ensure_user_spaces
from app.api.invitation_service import accept_invitation, normalize_invite_code
from app.db.session import Database
from app.platforms.identity import PlatformIdentity, upsert_platform_user


async def accept_bot_invitation(
    database: Database,
    payload: str,
    max_user: dict,
) -> dict:
    user_id = max_user.get("user_id")
    if not isinstance(user_id, int):
        raise ValueError("MAX не передал идентификатор пользователя")
    display_name = str(max_user.get("name") or max_user.get("first_name") or "Пользователь MAX")[:160]
    username = max_user.get("username")
    return await accept_platform_invitation(
        database,
        payload,
        PlatformIdentity(
            provider="max",
            user_id=str(user_id),
            display_name=display_name,
            username=str(username)[:64] if username else None,
            locale="ru",
        ),
    )


async def accept_platform_invitation(
    database: Database,
    payload: str,
    identity: PlatformIdentity,
) -> dict:
    code = normalize_invite_code(payload)
    async with database.sessions.begin() as session:
        user = await upsert_platform_user(session, identity)
        await ensure_user_spaces(session, user)
        return await accept_invitation(session, code, user)
