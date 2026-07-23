from __future__ import annotations

import asyncio
import logging
import os
from collections.abc import Awaitable

from aiogram import Bot
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.client.telegram import TelegramAPIServer
from aiogram.exceptions import (
    TelegramBadRequest,
    TelegramForbiddenError,
    TelegramNetworkError,
    TelegramRetryAfter,
)
from dotenv import load_dotenv

from app.bots.broadcasts import (
    BroadcastPermanentError,
    BroadcastRetry,
    BroadcastWorker,
)
from app.db.session import Database
from app.platforms.max.api import MaxApiClient, MaxApiError


logger = logging.getLogger(__name__)


def _max_sender(api: MaxApiClient):
    async def send(provider_user_id: str, text: str) -> None:
        try:
            await api.send_text(text, user_id=int(provider_user_id))
        except MaxApiError as exc:
            if exc.status_code is None or exc.status_code == 429 or exc.status_code >= 500:
                raise BroadcastRetry(str(exc)) from exc
            raise BroadcastPermanentError(str(exc)) from exc

    return send


def _telegram_sender(bot: Bot):
    async def send(provider_user_id: str, text: str) -> None:
        try:
            await bot.send_message(chat_id=int(provider_user_id), text=text)
        except TelegramRetryAfter as exc:
            raise BroadcastRetry(
                "telegram_rate_limit",
                delay=float(exc.retry_after),
            ) from exc
        except TelegramNetworkError as exc:
            raise BroadcastRetry(str(exc)) from exc
        except (TelegramForbiddenError, TelegramBadRequest) as exc:
            raise BroadcastPermanentError(str(exc)) from exc

    return send


async def run() -> None:
    load_dotenv()
    database_url = os.getenv("DATABASE_URL", "").strip()
    max_token = os.getenv("MAX_BOT_TOKEN", "").strip()
    telegram_token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
    telegram_api_base_url = os.getenv("TELEGRAM_API_BASE_URL", "").strip()
    if not database_url:
        raise RuntimeError("DATABASE_URL не заполнен")
    if not max_token and not telegram_token:
        raise RuntimeError("Для рассылок нужен MAX_BOT_TOKEN или TELEGRAM_BOT_TOKEN")

    logging.basicConfig(
        level=os.getenv("LOG_LEVEL", "INFO"),
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    database = Database(database_url)
    await database.ping()
    closers: list[Awaitable[None]] = []
    workers: list[asyncio.Task[None]] = []

    if max_token:
        max_api = MaxApiClient(
            token=max_token,
            base_url=os.getenv("MAX_API_BASE_URL", "https://platform-api2.max.ru"),
            poll_timeout=int(os.getenv("MAX_POLL_TIMEOUT", "30")),
        )
        closers.append(max_api.close())
        workers.append(
            asyncio.create_task(
                BroadcastWorker(database, "max", _max_sender(max_api)).run(),
                name="broadcast-max",
            )
        )

    if telegram_token:
        telegram_session = (
            AiohttpSession(api=TelegramAPIServer.from_base(telegram_api_base_url))
            if telegram_api_base_url
            else AiohttpSession()
        )
        telegram_bot = Bot(token=telegram_token, session=telegram_session)
        closers.append(telegram_bot.session.close())
        workers.append(
            asyncio.create_task(
                BroadcastWorker(
                    database,
                    "telegram",
                    _telegram_sender(telegram_bot),
                ).run(),
                name="broadcast-telegram",
            )
        )

    logger.info("Broadcast service started channels=%s", len(workers))
    try:
        await asyncio.gather(*workers)
    finally:
        for task in workers:
            task.cancel()
        await asyncio.gather(*workers, return_exceptions=True)
        await asyncio.gather(*closers, return_exceptions=True)
        await database.dispose()


if __name__ == "__main__":
    asyncio.run(run())
