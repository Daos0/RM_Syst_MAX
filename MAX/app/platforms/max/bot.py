import asyncio
import logging
import os
from typing import Any
from uuid import UUID

from dotenv import load_dotenv

from app.api.auth_routes import ensure_user_spaces
from app.api.bot_invitation import accept_bot_invitation
from app.api.invitation_service import InvitationError
from app.bots.lists import list_page_for_bot
from app.bots.shopping import (
    BotShoppingError,
    set_item_status_from_bot,
    shopping_page_for_bot,
)
from app.bots.texts import CABINET_TEXT, HELP_TEXT, PURCHASES_TEXT, WELCOME_TEXT
from app.db.session import Database
from app.platforms.identity import PlatformIdentity, upsert_platform_user
from app.platforms.max.api import MaxApiClient, MaxApiError

logger = logging.getLogger(__name__)

MENU_CALLBACKS = {"start", "start_purchases", "personal_cabinet", "show_lists", "help"}
MENU_COMMANDS = {"/start", "/lists", "/purchases", "/cabinet", "/help"}


def _max_identity(raw_user: object) -> PlatformIdentity | None:
    if not isinstance(raw_user, dict):
        return None
    user_id = raw_user.get("user_id")
    if not isinstance(user_id, int):
        return None
    display_name = str(
        raw_user.get("name")
        or " ".join(
            str(part)
            for part in (raw_user.get("first_name"), raw_user.get("last_name"))
            if part
        ).strip()
        or raw_user.get("username")
        or f"Пользователь {user_id}"
    )[:160]
    username = raw_user.get("username")
    avatar_url = raw_user.get("avatar_url")
    return PlatformIdentity(
        provider="max",
        user_id=str(user_id),
        display_name=display_name,
        username=str(username)[:64] if username else None,
        avatar_url=str(avatar_url)[:512] if avatar_url else None,
        locale="ru",
    )


class MaxShoppingBot:
    def __init__(self, api: MaxApiClient, database: Database | None = None) -> None:
        self._api = api
        self._database = database
        self.username: str | None = None

    async def prepare(self) -> None:
        bot = await self._api.get_me()
        self.username = bot.get("username")
        if await self._api.has_webhook_subscriptions():
            raise RuntimeError(
                "У бота есть активный Webhook. Удалите его перед локальным Long Polling."
            )
        await self._api.set_commands()

    async def run(self) -> None:
        marker: int | None = None
        logger.info("MAX bot polling started username=%s", self.username)
        while True:
            try:
                result = await self._api.get_updates(marker)
                updates = result.get("updates", [])
                if isinstance(updates, list):
                    for update in updates:
                        if isinstance(update, dict):
                            try:
                                await self.handle_update(update)
                            except MaxApiError as exc:
                                if exc.status_code is None or exc.status_code >= 500:
                                    raise
                                logger.warning(
                                    "MAX rejected update action operation=%s status=%s; skip update",
                                    exc.operation,
                                    exc.status_code,
                                )
                next_marker = result.get("marker")
                if isinstance(next_marker, int):
                    marker = next_marker
            except asyncio.CancelledError:
                raise
            except MaxApiError as exc:
                logger.warning(
                    "MAX API error operation=%s status=%s; retry in 3 seconds",
                    exc.operation,
                    exc.status_code,
                )
                await asyncio.sleep(3)

    async def handle_update(self, update: dict[str, Any]) -> None:
        update_type = update.get("update_type")
        if update_type == "bot_started":
            await self._remember_user(update.get("user"))
            chat_id = update.get("chat_id")
            if isinstance(chat_id, int):
                payload = update.get("payload")
                user = update.get("user")
                if (
                    isinstance(payload, str)
                    and payload.lower().startswith(("join_", "join-"))
                    and isinstance(user, dict)
                    and self._database is not None
                ):
                    try:
                        result = await accept_bot_invitation(self._database, payload, user)
                        if result.get("kind") == "family":
                            text = (
                                "Семейная группа подключена. Все её списки теперь доступны "
                                "в вашем кабинете."
                                if result.get("joined")
                                else "Вы уже состоите в этой семейной группе."
                            )
                            if result.get("list_id"):
                                await self._api.send_invitation_menu(
                                    text,
                                    result["list_id"],
                                    chat_id=chat_id,
                                    primary_text="Открыть семейные покупки",
                                )
                            else:
                                await self._api.send_menu(
                                    text,
                                    chat_id=chat_id,
                                    primary_text="Открыть кабинет",
                                    primary_payload="cabinet",
                                )
                        else:
                            text = (
                                f"Вы присоединились к покупке «{result['title']}». "
                                "Список уже доступен — можно начинать."
                                if result.get("joined")
                                else f"Покупка «{result['title']}» уже есть в ваших списках."
                            )
                            await self._api.send_invitation_menu(
                                text,
                                result["list_id"],
                                chat_id=chat_id,
                            )
                    except (InvitationError, ValueError) as exc:
                        await self._api.send_menu(
                            f"Не удалось принять приглашение: {exc}. Попросите отправить новую ссылку.",
                            chat_id=chat_id,
                        )
                    return
                await self._api.send_menu(WELCOME_TEXT, chat_id=chat_id)
            return

        if update_type == "message_callback":
            callback = update.get("callback")
            if not isinstance(callback, dict):
                return
            await self._remember_user(callback.get("user"))
            payload = callback.get("payload")
            callback_id = callback.get("callback_id")
            if not isinstance(payload, str) or not isinstance(callback_id, str) or not callback_id:
                return
            if payload == "home":
                await self._api.answer_menu_callback(callback_id, WELCOME_TEXT)
                return
            if payload == "help":
                await self._api.answer_help_callback(callback_id, HELP_TEXT)
                return
            if payload == "sp:0" or payload.startswith(("sp:", "sl:", "si:")):
                await self._handle_shopping_callback(
                    payload,
                    callback_id,
                    self._callback_user_id(callback),
                )
                return
            if payload in MENU_CALLBACKS:
                await self._api.acknowledge_callback(callback_id, "Меню открыто")
                target = self._message_target(update.get("message"))
                if target is None:
                    user = callback.get("user")
                    user_id = user.get("user_id") if isinstance(user, dict) else None
                    if isinstance(user_id, int):
                        target = {"user_id": user_id}
                if target is not None:
                    await self._send_action(
                        str(callback.get("payload")),
                        target,
                        self._callback_user_id(callback),
                    )
            return

        if update_type != "message_created":
            return
        message = update.get("message")
        if not isinstance(message, dict):
            return
        await self._remember_user(message.get("sender"))
        body = message.get("body")
        text = body.get("text") if isinstance(body, dict) else None
        if not isinstance(text, str):
            return
        normalized_text = text.strip().lower()
        command = normalized_text.split(maxsplit=1)[0].split("@", maxsplit=1)[0]
        if command not in MENU_COMMANDS:
            return

        target = self._message_target(message)
        if target is not None:
            await self._send_action(command, target, self._message_user_id(message))

    async def _remember_user(self, raw_user: object) -> None:
        identity = _max_identity(raw_user)
        if identity is None or self._database is None:
            return
        async with self._database.sessions.begin() as session:
            user = await upsert_platform_user(session, identity)
            await ensure_user_spaces(session, user)

    async def _send_action(
        self,
        action: str,
        target: dict[str, int],
        max_user_id: int | None,
    ) -> None:
        if action in {"/lists", "show_lists"}:
            await self._send_lists(target, max_user_id)
            return
        if action in {"/cabinet", "personal_cabinet"}:
            await self._api.send_menu(
                CABINET_TEXT,
                **target,
                primary_text="Открыть кабинет",
                primary_payload="cabinet",
            )
            return
        if action in {"/help", "help"}:
            await self._api.send_help_menu(HELP_TEXT, **target)
            return
        if action in {"/purchases", "start_purchases"}:
            await self._api.send_menu(PURCHASES_TEXT, **target)
            return
        await self._api.send_menu(WELCOME_TEXT, **target)

    async def _send_lists(
        self,
        target: dict[str, int],
        max_user_id: int | None,
    ) -> None:
        page_data = {"lists": [], "page": 0, "total_pages": 1, "total": 0}
        if self._database is not None and max_user_id is not None:
            page_data = await list_page_for_bot(self._database, max_user_id)
        if page_data["lists"]:
            await self._api.send_list_menu(
                self._lists_text(page_data),
                page_data["lists"],
                page=page_data["page"],
                total_pages=page_data["total_pages"],
                **target,
            )
            return
        await self._api.send_menu(
            "Списков пока нет. Откройте Mini App и создайте первый.",
            **target,
            primary_text="Открыть списки",
            primary_payload="lists",
        )

    async def _handle_shopping_callback(
        self,
        payload: str,
        callback_id: str,
        max_user_id: int | None,
    ) -> None:
        if self._database is None or max_user_id is None:
            await self._api.acknowledge_callback(
                callback_id, "Не удалось определить пользователя"
            )
            return
        try:
            parts = payload.split(":")
            if parts[0] == "sp" and len(parts) == 2:
                page_data = await list_page_for_bot(
                    self._database, max_user_id, page=int(parts[1])
                )
                await self._api.answer_list_callback(
                    callback_id,
                    self._lists_text(page_data),
                    page_data["lists"],
                    page=page_data["page"],
                    total_pages=page_data["total_pages"],
                )
                return

            if parts[0] == "sl" and len(parts) == 3:
                shopping_page = await shopping_page_for_bot(
                    self._database,
                    max_user_id,
                    UUID(parts[1]),
                    int(parts[2]),
                )
                await self._api.answer_shopping_callback(callback_id, shopping_page)
                return

            if parts[0] == "si" and len(parts) == 4:
                desired_status = {"p": "purchased", "a": "active"}.get(parts[2])
                if desired_status is None:
                    raise ValueError("unknown item state")
                result = await set_item_status_from_bot(
                    self._database,
                    max_user_id,
                    UUID(parts[1]),
                    desired_status,
                )
                shopping_page = await shopping_page_for_bot(
                    self._database,
                    max_user_id,
                    UUID(result["list_id"]),
                    int(parts[3]),
                )
                notification = (
                    f"Куплено: {result['name']}"
                    if result["status"] == "purchased"
                    else f"Возвращено в список: {result['name']}"
                )
                await self._api.answer_shopping_callback(
                    callback_id,
                    shopping_page,
                    notification,
                )
                return
            raise ValueError("unknown callback")
        except BotShoppingError as exc:
            await self._api.acknowledge_callback(callback_id, str(exc))
        except (TypeError, ValueError):
            await self._api.acknowledge_callback(
                callback_id, "Кнопка устарела — откройте списки заново"
            )

    @staticmethod
    def _lists_text(page_data: dict) -> str:
        if not page_data["total"]:
            return "Списков пока нет. Создайте первый в Mini App."
        text = "Ваши списки\nВыберите список — он откроется прямо в чате."
        if page_data["total_pages"] > 1:
            text += f"\nСтраница {page_data['page'] + 1} из {page_data['total_pages']}"
        return text

    @staticmethod
    def _callback_user_id(callback: dict[str, Any]) -> int | None:
        user = callback.get("user")
        user_id = user.get("user_id") if isinstance(user, dict) else None
        return user_id if isinstance(user_id, int) else None

    @staticmethod
    def _message_user_id(message: dict[str, Any]) -> int | None:
        sender = message.get("sender")
        user_id = sender.get("user_id") if isinstance(sender, dict) else None
        return user_id if isinstance(user_id, int) else None

    @staticmethod
    def _message_target(message: object) -> dict[str, int] | None:
        if not isinstance(message, dict):
            return None
        recipient = message.get("recipient")
        if isinstance(recipient, dict):
            chat_id = recipient.get("chat_id")
            if isinstance(chat_id, int):
                return {"chat_id": chat_id}
            user_id = recipient.get("user_id")
            if isinstance(user_id, int):
                return {"user_id": user_id}
        sender = message.get("sender")
        user_id = sender.get("user_id") if isinstance(sender, dict) else None
        if isinstance(user_id, int):
            return {"user_id": user_id}
        return None


async def run() -> None:
    load_dotenv()
    token = os.getenv("MAX_BOT_TOKEN", "").strip()
    database_url = os.getenv("DATABASE_URL", "").strip()
    if not token:
        raise RuntimeError("MAX_BOT_TOKEN не заполнен")
    if not database_url:
        raise RuntimeError("DATABASE_URL не заполнен")

    logging.basicConfig(
        level=os.getenv("LOG_LEVEL", "INFO"),
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    database = Database(database_url)
    api = MaxApiClient(
        token=token,
        base_url=os.getenv("MAX_API_BASE_URL", "https://platform-api2.max.ru"),
        poll_timeout=int(os.getenv("MAX_POLL_TIMEOUT", "30")),
    )
    try:
        await database.ping()
        application = MaxShoppingBot(api, database)
        await application.prepare()
        await application.run()
    finally:
        await api.close()
        await database.dispose()


if __name__ == "__main__":
    asyncio.run(run())
