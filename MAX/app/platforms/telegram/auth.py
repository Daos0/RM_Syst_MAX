from __future__ import annotations

import hashlib
import hmac
import json
import time
from urllib.parse import parse_qsl

from app.platforms.identity import PlatformIdentity


class TelegramInitDataError(ValueError):
    pass


def validate_telegram_init_data(
    init_data: str,
    bot_token: str,
    *,
    max_age_seconds: int = 3600,
) -> PlatformIdentity:
    if not bot_token:
        raise TelegramInitDataError("Токен Telegram-бота не настроен")
    pairs = parse_qsl(init_data, keep_blank_values=True, strict_parsing=True)
    params: dict[str, str] = {}
    for key, value in pairs:
        if key in params:
            raise TelegramInitDataError("Параметры запуска Telegram повторяются")
        params[key] = value
    received_hash = params.pop("hash", "")
    if not received_hash:
        raise TelegramInitDataError("Подпись Telegram отсутствует")
    data_check_string = "\n".join(f"{key}={params[key]}" for key in sorted(params))
    secret_key = hmac.new(b"WebAppData", bot_token.encode(), hashlib.sha256).digest()
    expected_hash = hmac.new(
        secret_key, data_check_string.encode(), hashlib.sha256
    ).hexdigest()
    if not hmac.compare_digest(received_hash, expected_hash):
        raise TelegramInitDataError("Подпись Telegram недействительна")

    try:
        auth_date = int(params["auth_date"])
    except (KeyError, TypeError, ValueError) as exc:
        raise TelegramInitDataError("Дата авторизации Telegram некорректна") from exc
    now = int(time.time())
    if auth_date > now + 60 or now - auth_date > max_age_seconds:
        raise TelegramInitDataError("Данные запуска Telegram устарели")

    try:
        user = json.loads(params["user"])
        provider_user_id = str(int(user["id"]))
    except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
        raise TelegramInitDataError("Пользователь Telegram не определён") from exc

    first_name = str(user.get("first_name") or "").strip()
    last_name = str(user.get("last_name") or "").strip()
    username = str(user.get("username") or "").strip() or None
    display_name = " ".join(part for part in (first_name, last_name) if part)
    if not display_name:
        display_name = username or f"Пользователь {provider_user_id}"
    return PlatformIdentity(
        provider="telegram",
        user_id=provider_user_id,
        display_name=display_name[:160],
        username=username[:64] if username else None,
        avatar_url=str(user.get("photo_url") or "").strip() or None,
        locale=str(user.get("language_code") or "ru")[:12],
    )
