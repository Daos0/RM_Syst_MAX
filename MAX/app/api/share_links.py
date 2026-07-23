from __future__ import annotations

from urllib.parse import quote


def invitation_links(
    *,
    code: str,
    message: str,
    max_username: str | None = None,
    telegram_username: str | None = None,
) -> tuple[dict[str, str], dict[str, str]]:
    bot_urls: dict[str, str] = {}
    share_urls: dict[str, str] = {}
    if max_username:
        max_url = f"https://max.ru/{max_username.lstrip('@')}?start=join_{code}"
        max_share_text = f"{message}\n{max_url}\nКод: {code}"
        bot_urls["max"] = max_url
        share_urls["max"] = (
            f"https://max.ru/:share?text={quote(max_share_text, safe='')}"
        )
    if telegram_username:
        telegram_url = (
            f"https://t.me/{telegram_username.lstrip('@')}?start=join_{code}"
        )
        telegram_share_text = f"{message}\nКод: {code}"
        bot_urls["telegram"] = telegram_url
        share_urls["telegram"] = (
            "https://t.me/share/url?"
            f"url={quote(telegram_url, safe='')}&text={quote(telegram_share_text, safe='')}"
        )
    return bot_urls, share_urls
