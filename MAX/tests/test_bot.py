import asyncio
from unittest.mock import AsyncMock, patch
from uuid import uuid4

from app.bots.texts import CABINET_TEXT, HELP_TEXT, WELCOME_TEXT
from app.platforms.max.api import MaxApiClient
from app.platforms.max.bot import MaxShoppingBot, _max_identity


class FakeApi:
    def __init__(self) -> None:
        self.menus: list[dict[str, object]] = []
        self.list_menus: list[dict[str, object]] = []
        self.answered_lists: list[dict[str, object]] = []
        self.answered_shopping: list[dict[str, object]] = []
        self.help_menus: list[dict[str, object]] = []
        self.answered_menus: list[dict[str, object]] = []
        self.answered_help: list[dict[str, object]] = []
        self.callback_ids: list[tuple[str, str]] = []

    async def send_menu(self, text: str, **target: object) -> None:
        self.menus.append({"text": text, **target})

    async def send_list_menu(self, text: str, lists: list[dict], **target: object) -> None:
        self.list_menus.append({"text": text, "lists": lists, **target})

    async def send_help_menu(self, text: str, **target: object) -> None:
        self.help_menus.append({"text": text, **target})

    async def acknowledge_callback(self, callback_id: str, notification: str) -> None:
        self.callback_ids.append((callback_id, notification))

    async def answer_list_callback(
        self, callback_id: str, text: str, lists: list[dict], **options: object
    ) -> None:
        self.answered_lists.append(
            {"callback_id": callback_id, "text": text, "lists": lists, **options}
        )

    async def answer_shopping_callback(
        self, callback_id: str, shopping_page: dict, notification: str | None = None
    ) -> None:
        self.answered_shopping.append(
            {
                "callback_id": callback_id,
                "shopping_page": shopping_page,
                "notification": notification,
            }
        )

    async def answer_menu_callback(self, callback_id: str, text: str) -> None:
        self.answered_menus.append({"callback_id": callback_id, "text": text})

    async def answer_help_callback(self, callback_id: str, text: str) -> None:
        self.answered_help.append({"callback_id": callback_id, "text": text})


def test_bot_started_sends_main_menu() -> None:
    api = FakeApi()
    bot = MaxShoppingBot(api)  # type: ignore[arg-type]

    asyncio.run(bot.handle_update({"update_type": "bot_started", "chat_id": 42}))

    assert api.menus == [{"text": WELCOME_TEXT, "chat_id": 42}]


def test_max_identity_is_created_from_bot_update_user() -> None:
    identity = _max_identity(
        {
            "user_id": 77,
            "first_name": "Роман",
            "last_name": "Михайлов",
            "username": "roman",
        }
    )

    assert identity is not None
    assert identity.provider == "max"
    assert identity.user_id == "77"
    assert identity.display_name == "Роман Михайлов"
    assert identity.username == "roman"


def test_other_updates_are_ignored() -> None:
    api = FakeApi()
    bot = MaxShoppingBot(api)  # type: ignore[arg-type]

    asyncio.run(bot.handle_update({"update_type": "message_created", "chat_id": 42}))

    assert api.menus == []


def test_help_callback_opens_help() -> None:
    api = FakeApi()
    bot = MaxShoppingBot(api)  # type: ignore[arg-type]

    asyncio.run(
        bot.handle_update(
            {
                "update_type": "message_callback",
                "callback": {
                    "callback_id": "callback-123",
                    "payload": "help",
                },
                "message": {"recipient": {"chat_id": 42}},
            }
        )
    )

    assert api.callback_ids == []
    assert api.answered_help == [
        {"callback_id": "callback-123", "text": HELP_TEXT}
    ]
    assert "Роман Михайлов" in HELP_TEXT
    assert "Mini Apps" in HELP_TEXT


def test_back_from_lists_restores_main_menu_in_same_message() -> None:
    api = FakeApi()
    bot = MaxShoppingBot(api)  # type: ignore[arg-type]

    asyncio.run(
        bot.handle_update(
            {
                "update_type": "message_callback",
                "callback": {
                    "callback_id": "callback-home",
                    "payload": "home",
                    "user": {"user_id": 7},
                },
            }
        )
    )

    assert api.answered_menus == [
        {"callback_id": "callback-home", "text": WELCOME_TEXT}
    ]


def test_cabinet_command_gets_test_answer() -> None:
    api = FakeApi()
    bot = MaxShoppingBot(api)  # type: ignore[arg-type]

    asyncio.run(
        bot.handle_update(
            {
                "update_type": "message_created",
                "message": {
                    "sender": {"user_id": 7},
                    "recipient": {"chat_id": 42},
                    "body": {"text": "/cabinet"},
                },
            }
        )
    )

    assert api.menus == [
        {
            "text": CABINET_TEXT,
            "chat_id": 42,
            "primary_text": "Открыть кабинет",
            "primary_payload": "cabinet",
        }
    ]


def test_open_app_keyboard_contains_bot_identity() -> None:
    api = object.__new__(MaxApiClient)
    api._web_app = "shopping_bot"
    api._contact_id = 77

    buttons = api._menu_message("Меню")["attachments"][0]["payload"]["buttons"]

    assert buttons[0][0] == {
        "type": "callback",
        "text": "Мои списки",
        "payload": "sp:0",
    }
    assert [button["text"] for button in buttons[1]] == ["Добавить список", "Кабинет"]
    assert buttons[2] == [
        {"type": "callback", "text": "Помощь", "payload": "help"}
    ]
    assert buttons[1][1]["contact_id"] == 77


def test_help_contains_project_context_before_contact() -> None:
    api = object.__new__(MaxApiClient)
    api._web_app = "shopping_bot"
    api._contact_id = 77

    buttons = api._help_message(HELP_TEXT)["attachments"][0]["payload"]["buttons"]

    assert buttons == [
        [
            {
                "type": "link",
                "text": "Роман Михайлов · RM Systems",
                "url": "https://rm-syst.ru/",
            }
        ],
        [{"type": "callback", "text": "← Главная", "payload": "home"}],
    ]
    assert "О ПРОЕКТЕ" in HELP_TEXT
    assert "/lists" not in HELP_TEXT


def test_list_keyboard_opens_each_list() -> None:
    api = object.__new__(MaxApiClient)
    api._web_app = "shopping_bot"
    api._contact_id = 77

    message = api._list_message(
        "Ваши списки",
        [
            {
                "id": "12345678-1234-5678-1234-567812345678",
                "title": "Поход",
                "item_count": 8,
                "purchased_count": 2,
            }
        ],
    )
    buttons = message["attachments"][0]["payload"]["buttons"]

    assert buttons[0][0]["text"] == "Поход · 2/8"
    assert buttons[0][0]["type"] == "callback"
    assert buttons[0][0]["payload"] == "sl:12345678123456781234567812345678:0"
    assert buttons[-1] == [
        {"type": "callback", "text": "← Главная", "payload": "home"}
    ]


def test_shopping_keyboard_uses_idempotent_item_action() -> None:
    api = object.__new__(MaxApiClient)
    api._web_app = "shopping_bot"
    api._contact_id = 77
    list_id = "12345678-1234-5678-1234-567812345678"
    item_id = "87654321-4321-8765-4321-876543218765"

    message = api._shopping_message(
        {
            "id": list_id,
            "title": "Поход",
            "total": 2,
            "purchased": 1,
            "page": 0,
            "total_pages": 1,
            "items": [
                {
                    "id": item_id,
                    "name": "Молоко",
                    "quantity": "2 л",
                    "status": "active",
                }
            ],
        }
    )
    buttons = message["attachments"][0]["payload"]["buttons"]

    assert "Куплено 1 из 2 · 50%" in message["text"]
    assert buttons[0][0]["text"] == "⬜ Молоко · 2 л"
    assert buttons[0][0]["payload"] == "si:87654321432187654321876543218765:p:0"
    assert buttons[-1][0]["payload"] == "sp:0"
    assert buttons[-1][0]["text"] == "← Мои списки"


def test_item_callback_updates_message_in_place() -> None:
    api = FakeApi()
    bot = MaxShoppingBot(api, object())  # type: ignore[arg-type]
    item_id = uuid4()
    list_id = uuid4()
    page = {
        "id": str(list_id),
        "title": "Поход",
        "total": 1,
        "purchased": 1,
        "page": 0,
        "total_pages": 1,
        "items": [],
    }

    with (
        patch.object(bot, "_remember_user", new=AsyncMock()),
        patch(
            "app.platforms.max.bot.set_item_status_from_bot",
            new=AsyncMock(
                return_value={
                    "list_id": str(list_id),
                    "name": "Молоко",
                    "status": "purchased",
                    "changed": True,
                }
            ),
        ),
        patch(
            "app.platforms.max.bot.shopping_page_for_bot",
            new=AsyncMock(return_value=page),
        ),
    ):
        asyncio.run(
            bot.handle_update(
                {
                    "update_type": "message_callback",
                    "callback": {
                        "callback_id": "callback-item",
                        "payload": f"si:{item_id.hex}:p:0",
                        "user": {"user_id": 7},
                    },
                }
            )
        )

    assert api.answered_shopping == [
        {
            "callback_id": "callback-item",
            "shopping_page": page,
            "notification": "Куплено: Молоко",
        }
    ]
