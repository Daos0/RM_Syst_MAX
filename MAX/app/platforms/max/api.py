import ssl
from pathlib import Path
from typing import Any

import httpx


class MaxApiError(RuntimeError):
    def __init__(self, operation: str, status_code: int | None = None) -> None:
        self.operation = operation
        self.status_code = status_code
        super().__init__(operation)


class MaxApiClient:
    def __init__(self, token: str, base_url: str, poll_timeout: int = 30) -> None:
        if not token:
            raise RuntimeError("MAX_BOT_TOKEN не заполнен в .env")

        certificate = (
            Path(__file__).resolve().parents[2]
            / "certs"
            / "russian_trusted_root_ca.pem"
        )
        ssl_context = ssl.create_default_context()
        ssl_context.load_verify_locations(cafile=certificate)

        self._poll_timeout = poll_timeout
        self._web_app: str | None = None
        self._contact_id: int | None = None
        self._client = httpx.AsyncClient(
            base_url=base_url.rstrip("/"),
            headers={"Authorization": token, "User-Agent": "max-start-bot/0.1"},
            timeout=httpx.Timeout(connect=10, read=poll_timeout + 10, write=10, pool=10),
            verify=ssl_context,
        )

    async def close(self) -> None:
        await self._client.aclose()

    async def _request(self, method: str, path: str, **kwargs: Any) -> dict[str, Any] | list[Any]:
        try:
            response = await self._client.request(method, path, **kwargs)
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as exc:
            raise MaxApiError(path, exc.response.status_code) from exc
        except (httpx.HTTPError, ValueError) as exc:
            raise MaxApiError(path) from exc

    async def get_me(self) -> dict[str, Any]:
        result = await self._request("GET", "/me")
        if not isinstance(result, dict):
            raise MaxApiError("/me")
        username = result.get("username")
        user_id = result.get("user_id")
        self._web_app = username if isinstance(username, str) else None
        self._contact_id = user_id if isinstance(user_id, int) else None
        return result

    async def has_webhook_subscriptions(self) -> bool:
        result = await self._request("GET", "/subscriptions")
        if isinstance(result, list):
            return bool(result)
        subscriptions = result.get("subscriptions", [])
        return bool(subscriptions)

    async def set_commands(self) -> None:
        await self._request(
            "PATCH",
            "/me/commands",
            json={
                "commands": [
                    {"name": "/start", "description": "Главное меню"},
                    {"name": "/lists", "description": "Мои списки"},
                    {"name": "/cabinet", "description": "Личный кабинет"},
                    {"name": "/help", "description": "Помощь"},
                ]
            },
        )

    async def get_updates(self, marker: int | None) -> dict[str, Any]:
        params: dict[str, Any] = {
            "limit": 100,
            "timeout": self._poll_timeout,
            "types": "bot_started,message_callback,message_created",
        }
        if marker is not None:
            params["marker"] = marker
        result = await self._request("GET", "/updates", params=params)
        if not isinstance(result, dict):
            raise MaxApiError("/updates")
        return result

    async def send_menu(
        self,
        text: str,
        *,
        chat_id: int | None = None,
        user_id: int | None = None,
        primary_text: str | None = None,
        primary_payload: str = "purchases",
    ) -> None:
        if (chat_id is None) == (user_id is None):
            raise ValueError("Укажите ровно один chat_id или user_id")
        params = {"chat_id": chat_id} if chat_id is not None else {"user_id": user_id}
        await self._request(
            "POST",
            "/messages",
            params=params,
            json=self._menu_message(
                text,
                primary_text=primary_text,
                primary_payload=primary_payload,
            ),
        )

    async def send_text(self, text: str, *, user_id: int) -> None:
        await self._request(
            "POST",
            "/messages",
            params={"user_id": user_id},
            json={"text": text},
        )

    async def send_list_menu(
        self,
        text: str,
        lists: list[dict],
        *,
        page: int = 0,
        total_pages: int = 1,
        chat_id: int | None = None,
        user_id: int | None = None,
    ) -> None:
        if (chat_id is None) == (user_id is None):
            raise ValueError("Укажите ровно один chat_id или user_id")
        params = {"chat_id": chat_id} if chat_id is not None else {"user_id": user_id}
        await self._request(
            "POST",
            "/messages",
            params=params,
            json=self._list_message(text, lists, page=page, total_pages=total_pages),
        )

    async def send_help_menu(
        self,
        text: str,
        *,
        chat_id: int | None = None,
        user_id: int | None = None,
    ) -> None:
        if (chat_id is None) == (user_id is None):
            raise ValueError("Укажите ровно один chat_id или user_id")
        params = {"chat_id": chat_id} if chat_id is not None else {"user_id": user_id}
        await self._request(
            "POST",
            "/messages",
            params=params,
            json=self._help_message(text),
        )

    async def send_invitation_menu(
        self,
        text: str,
        list_id: str,
        *,
        chat_id: int | None = None,
        user_id: int | None = None,
        primary_text: str = "Открыть совместную покупку",
    ) -> None:
        if (chat_id is None) == (user_id is None):
            raise ValueError("Укажите ровно один chat_id или user_id")
        params = {"chat_id": chat_id} if chat_id is not None else {"user_id": user_id}
        body = self._menu_message(
            text,
            primary_text=primary_text,
            primary_payload=f"open_{list_id}",
        )
        await self._request("POST", "/messages", params=params, json=body)

    async def acknowledge_callback(self, callback_id: str, notification: str = "Готово") -> None:
        await self._request(
            "POST",
            "/answers",
            params={"callback_id": callback_id},
            json={"notification": notification},
        )

    async def answer_list_callback(
        self,
        callback_id: str,
        text: str,
        lists: list[dict],
        *,
        page: int = 0,
        total_pages: int = 1,
    ) -> None:
        await self._answer_callback(
            callback_id,
            self._list_message(text, lists, page=page, total_pages=total_pages),
        )

    async def answer_menu_callback(self, callback_id: str, text: str) -> None:
        await self._answer_callback(callback_id, self._menu_message(text))

    async def answer_help_callback(self, callback_id: str, text: str) -> None:
        await self._answer_callback(callback_id, self._help_message(text))

    async def answer_shopping_callback(
        self,
        callback_id: str,
        shopping_page: dict,
        notification: str | None = None,
    ) -> None:
        await self._answer_callback(
            callback_id,
            self._shopping_message(shopping_page),
            notification=notification,
        )

    async def _answer_callback(
        self,
        callback_id: str,
        message: dict[str, Any],
        *,
        notification: str | None = None,
    ) -> None:
        body: dict[str, Any] = {"message": message}
        if notification:
            body["notification"] = notification
        await self._request(
            "POST",
            "/answers",
            params={"callback_id": callback_id},
            json=body,
        )

    def _open_app_button(self, text: str, payload: str) -> dict[str, Any]:
        if not self._web_app:
            raise RuntimeError("MAX не вернул публичное имя бота для кнопки Mini App")
        button: dict[str, Any] = {
            "type": "open_app",
            "text": text,
            "web_app": self._web_app,
            "payload": payload,
        }
        if self._contact_id is not None:
            button["contact_id"] = self._contact_id
        return button

    @staticmethod
    def _callback_button(text: str, payload: str) -> dict[str, str]:
        return {"type": "callback", "text": text, "payload": payload}

    @staticmethod
    def _link_button(text: str, url: str) -> dict[str, str]:
        return {"type": "link", "text": text, "url": url}

    def _list_navigation_rows(self) -> list[list[dict[str, Any]]]:
        return [
            [
                self._open_app_button("Добавить список", "purchases"),
                self._open_app_button("Кабинет", "cabinet"),
            ],
            [self._callback_button("Помощь", "help")],
            [self._callback_button("← Главная", "home")],
        ]

    def _menu_message(
        self,
        text: str,
        *,
        primary_text: str | None = None,
        primary_payload: str = "purchases",
    ) -> dict[str, Any]:
        buttons: list[list[dict[str, Any]]] = []
        if primary_text:
            buttons.append([self._open_app_button(primary_text, primary_payload)])
        buttons.append([self._callback_button("Мои списки", "sp:0")])
        app_buttons = []
        if not primary_text or primary_payload != "purchases":
            app_buttons.append(self._open_app_button("Добавить список", "purchases"))
        if not primary_text or primary_payload != "cabinet":
            app_buttons.append(self._open_app_button("Кабинет", "cabinet"))
        if app_buttons:
            buttons.append(app_buttons)
        buttons.append([self._callback_button("Помощь", "help")])
        return {
            "text": text,
            "attachments": [
                {
                    "type": "inline_keyboard",
                    "payload": {"buttons": buttons},
                }
            ],
        }

    def _help_message(self, text: str) -> dict[str, Any]:
        return {
            "text": text,
            "attachments": [
                {
                    "type": "inline_keyboard",
                    "payload": {
                        "buttons": [
                            [
                                self._link_button(
                                    "Роман Михайлов · RM Systems",
                                    "https://rm-syst.ru/",
                                )
                            ],
                            [self._callback_button("← Главная", "home")],
                        ]
                    },
                }
            ],
        }

    def _list_message(
        self,
        text: str,
        lists: list[dict],
        *,
        page: int = 0,
        total_pages: int = 1,
    ) -> dict[str, Any]:
        rows = []
        for item in lists:
            title = str(item.get("title") or "Список")
            if len(title) > 20:
                title = f"{title[:19]}…"
            count = int(item.get("item_count") or 0)
            purchased = int(item.get("purchased_count") or 0)
            progress = f"{purchased}/{count}" if count else "пусто"
            label = f"{title} · {progress}"
            list_hex = str(item["id"]).replace("-", "")
            rows.append([self._callback_button(label, f"sl:{list_hex}:0")])
        if total_pages > 1:
            pager = []
            if page > 0:
                pager.append(self._callback_button("← Назад", f"sp:{page - 1}"))
            if page + 1 < total_pages:
                pager.append(self._callback_button("Далее →", f"sp:{page + 1}"))
            if pager:
                rows.append(pager)
        rows.extend(self._list_navigation_rows())
        return {
            "text": text,
            "attachments": [
                {"type": "inline_keyboard", "payload": {"buttons": rows}}
            ],
        }

    def _shopping_message(self, shopping_page: dict) -> dict[str, Any]:
        total = int(shopping_page.get("total") or 0)
        purchased = int(shopping_page.get("purchased") or 0)
        percent = round(purchased * 100 / total) if total else 0
        page = int(shopping_page.get("page") or 0)
        total_pages = int(shopping_page.get("total_pages") or 1)
        title = str(shopping_page.get("title") or "Список")
        text = f"{title}\nКуплено {purchased} из {total} · {percent}%"
        if total:
            text += "\n\nНажмите товар, чтобы отметить покупку или вернуть его в список."
            if total_pages > 1:
                text += f"\nСтраница {page + 1} из {total_pages}"
        else:
            text += "\n\nСписок пока пуст. Добавьте товары в Mini App."

        rows: list[list[dict[str, Any]]] = []
        for item in shopping_page.get("items", []):
            status = item.get("status")
            purchased_item = status == "purchased"
            icon = {
                "purchased": "✅",
                "unavailable": "🚫",
                "assigned": "👤",
            }.get(status, "⬜")
            name = str(item.get("name") or "Товар")
            if len(name) > 20:
                name = f"{name[:19]}…"
            quantity = str(item.get("quantity") or "")
            desired = "a" if purchased_item else "p"
            item_hex = str(item["id"]).replace("-", "")
            rows.append(
                [
                    self._callback_button(
                        f"{icon} {name} · {quantity}",
                        f"si:{item_hex}:{desired}:{page}",
                    )
                ]
            )

        if total_pages > 1:
            pager = []
            list_hex = str(shopping_page["id"]).replace("-", "")
            if page > 0:
                pager.append(self._callback_button("← Назад", f"sl:{list_hex}:{page - 1}"))
            if page + 1 < total_pages:
                pager.append(self._callback_button("Далее →", f"sl:{list_hex}:{page + 1}"))
            if pager:
                rows.append(pager)

        list_hex = str(shopping_page["id"]).replace("-", "")
        rows.append([self._callback_button("Обновить список", f"sl:{list_hex}:{page}")])
        rows.append(
            [self._open_app_button("Открыть в Mini App", f"open_{shopping_page['id']}")]
        )
        rows.append([self._callback_button("← Мои списки", "sp:0")])
        return {
            "text": text,
            "attachments": [
                {"type": "inline_keyboard", "payload": {"buttons": rows}}
            ],
        }
