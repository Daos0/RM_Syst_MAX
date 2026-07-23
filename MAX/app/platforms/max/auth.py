from __future__ import annotations

import hashlib
import hmac
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from urllib.parse import unquote


class MaxInitDataError(ValueError):
    pass


@dataclass(frozen=True)
class MaxIdentity:
    user_id: str
    display_name: str
    username: str | None
    locale: str
    avatar_url: str | None
    query_id: str | None


def _parse_pairs(init_data: str) -> dict[str, str]:
    pairs: dict[str, str] = {}
    for raw_pair in init_data.split("&"):
        if "=" not in raw_pair:
            raise MaxInitDataError("Некорректные данные запуска MAX")
        raw_key, raw_value = raw_pair.split("=", 1)
        key, value = unquote(raw_key), unquote(raw_value)
        if not key or key in pairs:
            raise MaxInitDataError("Параметры запуска MAX повторяются")
        pairs[key] = value
    return pairs


def validate_max_init_data(
    init_data: str,
    bot_token: str,
    *,
    max_age_seconds: int = 3600,
    now: datetime | None = None,
) -> MaxIdentity:
    if not bot_token:
        raise MaxInitDataError("Токен MAX-бота не настроен")
    pairs = _parse_pairs(init_data)
    received_hash = pairs.pop("hash", "")
    if len(received_hash) != 64:
        raise MaxInitDataError("Подпись MAX отсутствует")
    launch_params = "\n".join(f"{key}={pairs[key]}" for key in sorted(pairs))
    secret_key = hmac.new(b"WebAppData", bot_token.encode(), hashlib.sha256).digest()
    calculated_hash = hmac.new(
        secret_key, launch_params.encode(), hashlib.sha256
    ).hexdigest()
    if not hmac.compare_digest(calculated_hash, received_hash):
        raise MaxInitDataError("Подпись MAX недействительна")

    try:
        auth_date = datetime.fromtimestamp(int(pairs["auth_date"]), tz=timezone.utc)
    except (KeyError, TypeError, ValueError, OverflowError) as exc:
        raise MaxInitDataError("Дата авторизации MAX некорректна") from exc
    current_time = now or datetime.now(timezone.utc)
    age = (current_time - auth_date).total_seconds()
    if age < -60 or age > max_age_seconds:
        raise MaxInitDataError("Данные запуска MAX устарели")

    try:
        user = json.loads(pairs["user"])
        user_id = str(int(user["id"]))
    except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
        raise MaxInitDataError("Пользователь MAX не определён") from exc
    first_name = str(user.get("first_name") or "").strip()
    last_name = str(user.get("last_name") or "").strip()
    display_name = " ".join(part for part in (first_name, last_name) if part)
    if not display_name:
        display_name = str(user.get("username") or f"Пользователь {user_id}")
    return MaxIdentity(
        user_id=user_id,
        display_name=display_name[:160],
        username=str(user["username"])[:64] if user.get("username") else None,
        locale=str(user.get("language_code") or "ru")[:12],
        avatar_url=str(user["photo_url"]) if user.get("photo_url") else None,
        query_id=pairs.get("query_id"),
    )
