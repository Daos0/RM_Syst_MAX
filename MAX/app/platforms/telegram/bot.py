from __future__ import annotations

import asyncio
import base64
import logging
import os
from uuid import UUID

from aiogram import Bot, Dispatcher, F, Router
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.client.telegram import TelegramAPIServer
from dotenv import load_dotenv
from aiogram.filters import Command, CommandStart
from aiogram.filters.command import CommandObject
from aiogram.types import (
    BotCommand,
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    MenuButtonWebApp,
    Message,
    ReplyKeyboardRemove,
    User as TelegramUser,
    WebAppInfo,
)

from app.api.auth_routes import ensure_user_spaces
from app.api.bot_invitation import accept_platform_invitation
from app.api.invitation_service import InvitationError
from app.bots.lists import list_page_for_bot
from app.bots.shopping import (
    BotShoppingError,
    set_item_status_from_bot,
    shopping_page_for_bot,
)
from app.bots.texts import HELP_TEXT
from app.db.session import Database
from app.platforms.identity import PlatformIdentity, upsert_platform_user


logger = logging.getLogger(__name__)

TELEGRAM_HOME_TEXT = (
    "Покупки без путаницы\n\n"
    "Списки для себя, семьи и совместных покупок — в одном месте. "
    "Добавьте товар вручную или выберите блюдо: нужные продукты "
    "рассчитаются автоматически.\n\n"
    "Выберите, что хотите сделать:"
)


def _uuid_pack(value: str) -> str:
    return base64.urlsafe_b64encode(UUID(value).bytes).decode().rstrip("=")


def _uuid_unpack(value: str) -> UUID:
    return UUID(bytes=base64.urlsafe_b64decode(value + "=" * (-len(value) % 4)))


def _identity(user: TelegramUser) -> PlatformIdentity:
    name = " ".join(part for part in (user.first_name, user.last_name) if part).strip()
    return PlatformIdentity(
        provider="telegram",
        user_id=str(user.id),
        display_name=(name or user.username or f"Пользователь {user.id}")[:160],
        username=user.username,
        locale=(user.language_code or "ru")[:12],
    )


class TelegramShoppingBot:
    def __init__(self, bot: Bot, database: Database, mini_app_url: str) -> None:
        self.bot = bot
        self.database = database
        self.mini_app_url = mini_app_url
        self.router = Router(name="telegram-shopping")
        self._register_handlers()

    def _register_handlers(self) -> None:
        self.router.message.register(self.start, CommandStart())
        self.router.message.register(self.show_lists, Command("lists"))
        self.router.message.register(self.help, Command("help"))
        self.router.message.register(
            self.show_lists,
            F.text.in_({"Мои списки", "🧾 Мои списки"}),
        )
        self.router.message.register(
            self.help,
            F.text.in_({"Помощь", "ℹ️ Помощь"}),
        )
        self.router.callback_query.register(self.callback)

    async def prepare(self) -> None:
        await self.bot.delete_webhook(drop_pending_updates=False)
        await self.bot.set_my_commands(
            [
                BotCommand(command="start", description="Главное меню"),
                BotCommand(command="lists", description="Мои списки"),
                BotCommand(command="help", description="Краткая инструкция"),
            ]
        )
        await self.bot.set_chat_menu_button(
            menu_button=MenuButtonWebApp(
                text="Открыть покупки",
                web_app=WebAppInfo(url=self.mini_app_url),
            )
        )

    async def ensure_user(self, telegram_user: TelegramUser) -> None:
        async with self.database.sessions.begin() as session:
            user = await upsert_platform_user(session, _identity(telegram_user))
            await ensure_user_spaces(session, user)

    def home_markup(self) -> InlineKeyboardMarkup:
        return InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="🧾 Мои списки", callback_data="sp:0")],
                [
                    InlineKeyboardButton(
                        text="＋ Новый список",
                        web_app=WebAppInfo(url=f"{self.mini_app_url}?action=add-list"),
                    ),
                    InlineKeyboardButton(
                        text="👤 Кабинет",
                        web_app=WebAppInfo(url=f"{self.mini_app_url}?view=cabinet"),
                    ),
                ],
                [InlineKeyboardButton(text="ℹ️ Помощь", callback_data="help")],
            ]
        )

    async def start(self, message: Message, command: CommandObject) -> None:
        if message.from_user is None:
            return
        await self.ensure_user(message.from_user)
        payload = command.args or ""
        if payload.lower().startswith(("join_", "join-")):
            try:
                result = await accept_platform_invitation(
                    self.database, payload, _identity(message.from_user)
                )
                text = (
                    f"Покупка «{result['title']}» добавлена в ваши списки."
                    if result.get("kind") != "family"
                    else "Семейная группа подключена. Общие списки уже доступны."
                )
                await message.answer(text, reply_markup=self.home_markup())
                if result.get("list_id"):
                    await self._send_shopping(message, result["list_id"], 0)
                return
            except (InvitationError, ValueError) as exc:
                await message.answer(
                    f"Не удалось принять приглашение: {exc}",
                    reply_markup=self.home_markup(),
                )
                return
        await self._remove_legacy_reply_keyboard(message)
        await message.answer(TELEGRAM_HOME_TEXT, reply_markup=self.home_markup())

    async def help(self, message: Message) -> None:
        if message.from_user:
            await self.ensure_user(message.from_user)
        await message.answer(HELP_TEXT, reply_markup=self._back_markup())

    @staticmethod
    async def _remove_legacy_reply_keyboard(message: Message) -> None:
        """Однократно убирает клавиатуру, которую показывала предыдущая версия."""
        marker = await message.answer("Обновляю меню…", reply_markup=ReplyKeyboardRemove())
        try:
            await marker.delete()
        except Exception:  # pragma: no cover - удаление не влияет на работу меню
            logger.debug("Telegram did not delete keyboard migration marker")

    async def show_lists(self, message: Message) -> None:
        if message.from_user is None:
            return
        await self.ensure_user(message.from_user)
        page = await list_page_for_bot(
            self.database, message.from_user.id, provider="telegram"
        )
        await message.answer(
            self._lists_text(page),
            reply_markup=self._lists_markup(page),
        )

    async def callback(self, callback: CallbackQuery) -> None:
        if callback.from_user is None or callback.data is None:
            return
        await self.ensure_user(callback.from_user)
        data = callback.data
        try:
            if data == "home":
                await self._edit(callback, TELEGRAM_HOME_TEXT, self.home_markup())
            elif data == "help":
                await self._edit(callback, HELP_TEXT, self._back_markup())
            elif data.startswith("sp:"):
                page_number = int(data.split(":", 1)[1])
                page = await list_page_for_bot(
                    self.database,
                    callback.from_user.id,
                    page=page_number,
                    provider="telegram",
                )
                await self._edit(
                    callback, self._lists_text(page), self._lists_markup(page)
                )
            elif data.startswith("sl:"):
                _, packed_list, page_text = data.split(":", 2)
                await self._edit_shopping(
                    callback, _uuid_unpack(packed_list), int(page_text)
                )
            elif data.startswith("si:"):
                _, packed_item, desired, packed_list, page_text = data.split(":", 4)
                target_status = "purchased" if desired == "p" else "active"
                result = await set_item_status_from_bot(
                    self.database,
                    callback.from_user.id,
                    _uuid_unpack(packed_item),
                    target_status,
                    provider="telegram",
                )
                await self._edit_shopping(
                    callback,
                    _uuid_unpack(packed_list),
                    int(page_text),
                    notice=("Куплено" if result["status"] == "purchased" else "Возвращено"),
                )
            else:
                await callback.answer("Действие устарело", show_alert=False)
        except (BotShoppingError, ValueError):
            await callback.answer("Не удалось выполнить действие", show_alert=True)

    async def _send_shopping(self, message: Message, list_id: str, page: int) -> None:
        if message.from_user is None:
            return
        shopping = await shopping_page_for_bot(
            self.database,
            message.from_user.id,
            UUID(list_id),
            page,
            provider="telegram",
        )
        await message.answer(
            self._shopping_text(shopping),
            reply_markup=self._shopping_markup(shopping),
        )

    async def _edit_shopping(
        self,
        callback: CallbackQuery,
        list_id: UUID,
        page: int,
        notice: str | None = None,
    ) -> None:
        shopping = await shopping_page_for_bot(
            self.database,
            callback.from_user.id,
            list_id,
            page,
            provider="telegram",
        )
        await self._edit(
            callback,
            self._shopping_text(shopping),
            self._shopping_markup(shopping),
            notice,
        )

    @staticmethod
    async def _edit(
        callback: CallbackQuery,
        text: str,
        markup: InlineKeyboardMarkup,
        notice: str | None = None,
    ) -> None:
        if callback.message:
            await callback.message.edit_text(text, reply_markup=markup)
        await callback.answer(notice)

    @staticmethod
    def _lists_text(page: dict) -> str:
        if not page["lists"]:
            return "Мои списки\n\nЗдесь пока пусто. Создайте первый список."
        return "Мои списки\n\nНажмите на список — товары откроются прямо в чате."

    def _lists_markup(self, page: dict) -> InlineKeyboardMarkup:
        rows = []
        for item in page["lists"]:
            count = item["item_count"]
            progress = (
                f"{item['purchased_count']} из {count}"
                if count
                else "пустой"
            )
            rows.append(
                [
                    InlineKeyboardButton(
                        text=f"🛒 {item['title']} · {progress}",
                        callback_data=f"sl:{_uuid_pack(item['id'])}:0",
                    )
                ]
            )
        navigation = []
        if page["page"] > 0:
            navigation.append(
                InlineKeyboardButton(text="←", callback_data=f"sp:{page['page'] - 1}")
            )
        if page["page"] + 1 < page["total_pages"]:
            navigation.append(
                InlineKeyboardButton(text="→", callback_data=f"sp:{page['page'] + 1}")
            )
        if navigation:
            rows.append(navigation)
        rows.extend(
            [
                [
                    InlineKeyboardButton(
                        text="＋ Новый список",
                        web_app=WebAppInfo(url=f"{self.mini_app_url}?action=add-list"),
                    )
                ],
                [InlineKeyboardButton(text="← Главная", callback_data="home")],
            ]
        )
        return InlineKeyboardMarkup(inline_keyboard=rows)

    @staticmethod
    def _shopping_text(shopping: dict) -> str:
        return (
            f"{shopping['title']}\n\n"
            f"Куплено: {shopping['purchased']} из {shopping['total']}\n\n"
            "Нажмите на товар, чтобы отметить покупку."
        )

    def _shopping_markup(self, shopping: dict) -> InlineKeyboardMarkup:
        packed_list = _uuid_pack(shopping["id"])
        rows = []
        for item in shopping["items"]:
            purchased = item["status"] == "purchased"
            rows.append(
                [
                    InlineKeyboardButton(
                        text=("✅ " if purchased else "⬜ ")
                        + f"{item['name']} · {item['quantity']}",
                        callback_data=(
                            f"si:{_uuid_pack(item['id'])}:"
                            f"{'a' if purchased else 'p'}:{packed_list}:{shopping['page']}"
                        ),
                    )
                ]
            )
        navigation = []
        if shopping["page"] > 0:
            navigation.append(
                InlineKeyboardButton(
                    text="←",
                    callback_data=f"sl:{packed_list}:{shopping['page'] - 1}",
                )
            )
        if shopping["page"] + 1 < shopping["total_pages"]:
            navigation.append(
                InlineKeyboardButton(
                    text="→",
                    callback_data=f"sl:{packed_list}:{shopping['page'] + 1}",
                )
            )
        if navigation:
            rows.append(navigation)
        rows.extend(
            [
                [
                    InlineKeyboardButton(
                        text="Открыть в приложении",
                        web_app=WebAppInfo(
                            url=f"{self.mini_app_url}?list={shopping['id']}"
                        ),
                    )
                ],
                [InlineKeyboardButton(text="← Все списки", callback_data="sp:0")],
            ]
        )
        return InlineKeyboardMarkup(inline_keyboard=rows)

    @staticmethod
    def _back_markup() -> InlineKeyboardMarkup:
        return InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="Роман Михайлов · RM Systems", url="https://rm-syst.ru/"
                    )
                ],
                [InlineKeyboardButton(text="← Главная", callback_data="home")],
            ]
        )


async def run() -> None:
    load_dotenv()
    token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
    database_url = os.getenv("DATABASE_URL", "").strip()
    mini_app_url = os.getenv("TELEGRAM_MINI_APP_URL", "").strip()
    api_base_url = os.getenv("TELEGRAM_API_BASE_URL", "").strip()
    if not token:
        raise RuntimeError("TELEGRAM_BOT_TOKEN не заполнен")
    if not database_url:
        raise RuntimeError("DATABASE_URL не заполнен")
    if not mini_app_url.startswith("https://"):
        raise RuntimeError("TELEGRAM_MINI_APP_URL должен быть публичным HTTPS-адресом")

    logging.basicConfig(
        level=os.getenv("LOG_LEVEL", "INFO"),
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    database = Database(database_url)
    await database.ping()
    session = (
        AiohttpSession(api=TelegramAPIServer.from_base(api_base_url))
        if api_base_url
        else AiohttpSession()
    )
    bot = Bot(token=token, session=session)
    application = TelegramShoppingBot(bot, database, mini_app_url.rstrip("/"))
    dispatcher = Dispatcher()
    dispatcher.include_router(application.router)
    try:
        await application.prepare()
        me = await bot.get_me()
        logger.info("Telegram bot polling started username=%s", me.username)
        await dispatcher.start_polling(bot)
    finally:
        await bot.session.close()
        await database.dispose()


if __name__ == "__main__":
    asyncio.run(run())
