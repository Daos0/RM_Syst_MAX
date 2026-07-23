from __future__ import annotations

import hashlib
import hmac
import json
import os
import time
from unittest.mock import patch
from urllib.parse import urlencode
from uuid import uuid4

from fastapi.testclient import TestClient

from app.main import create_app
from app.platforms.telegram.auth import (
    TelegramInitDataError,
    validate_telegram_init_data,
)
from app.platforms.telegram.bot import TelegramShoppingBot
from app.platforms.telegram.bot import TELEGRAM_HOME_TEXT


TOKEN = "123456789:telegram-test-secret"
DATABASE_URL = os.environ.get("DATABASE_URL", "")


def signed_telegram_init_data(user_id: int, name: str, token: str = TOKEN) -> str:
    params = {
        "auth_date": str(int(time.time())),
        "query_id": uuid4().hex,
        "user": json.dumps(
            {
                "id": user_id,
                "first_name": name,
                "last_name": "",
                "username": "shopping_tester",
                "language_code": "ru",
            },
            ensure_ascii=False,
            separators=(",", ":"),
        ),
    }
    check_string = "\n".join(f"{key}={params[key]}" for key in sorted(params))
    secret = hmac.new(b"WebAppData", token.encode(), hashlib.sha256).digest()
    params["hash"] = hmac.new(secret, check_string.encode(), hashlib.sha256).hexdigest()
    return urlencode(params)


def test_telegram_init_data_validation() -> None:
    payload = signed_telegram_init_data(42, "Роман")
    identity = validate_telegram_init_data(payload, TOKEN)
    assert identity.provider == "telegram"
    assert identity.user_id == "42"
    assert identity.display_name == "Роман"

    forged = payload[:-1] + ("0" if payload[-1] != "0" else "1")
    try:
        validate_telegram_init_data(forged, TOKEN)
    except TelegramInitDataError:
        pass
    else:
        raise AssertionError("Поддельные Telegram initData были приняты")


def test_telegram_auth_uses_shared_account_api() -> None:
    if not DATABASE_URL:
        return
    application = create_app(
        database_enabled=True,
        database_url=DATABASE_URL,
    )
    user_id = int(uuid4().hex[:14], 16)
    with patch.dict(os.environ, {"TELEGRAM_BOT_TOKEN": TOKEN}):
        with TestClient(application) as client:
            response = client.post(
                "/api/v1/auth/telegram",
                json={"init_data": signed_telegram_init_data(user_id, "Telegram", TOKEN)},
            )
            assert response.status_code == 200, response.text
            payload = response.json()
            assert payload["active_platform"] == "telegram"
            assert payload["user"]["max_user_id"] is None
            assert payload["user"]["platforms"] == ["telegram"]
            assert {space["kind"] for space in payload["spaces"]} == {
                "personal",
                "family",
                "shared",
            }


def test_telegram_callback_data_fits_platform_limit() -> None:
    adapter = object.__new__(TelegramShoppingBot)
    adapter.mini_app_url = "https://example.com"
    markup = adapter._shopping_markup(
        {
            "id": str(uuid4()),
            "page": 0,
            "total_pages": 1,
            "items": [
                {
                    "id": str(uuid4()),
                    "name": "Очень длинное название товара",
                    "quantity": "1 шт.",
                    "status": "active",
                }
            ],
        }
    )
    callback_data = markup.inline_keyboard[0][0].callback_data
    assert callback_data is not None
    assert len(callback_data.encode()) <= 64


def test_telegram_home_is_compact_and_ordered() -> None:
    adapter = object.__new__(TelegramShoppingBot)
    adapter.mini_app_url = "https://example.com"

    assert "Выберите, с чего начать" not in TELEGRAM_HOME_TEXT
    assert TELEGRAM_HOME_TEXT.count("Выберите") == 1
    assert TELEGRAM_HOME_TEXT.endswith("Выберите, что хотите сделать:")

    inline_rows = adapter.home_markup().inline_keyboard
    assert [button.text for button in inline_rows[0]] == ["🧾 Мои списки"]
    assert [button.text for button in inline_rows[1]] == [
        "＋ Новый список",
        "👤 Кабинет",
    ]
    assert [button.text for button in inline_rows[2]] == ["ℹ️ Помощь"]
