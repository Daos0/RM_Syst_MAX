from __future__ import annotations

import asyncio
import os
from uuid import UUID, uuid4

from fastapi.testclient import TestClient
from sqlalchemy import delete, select

from app.bots.broadcasts import BroadcastWorker
from app.db.models import BroadcastCampaign, BroadcastRecipient
from app.db.session import Database
from app.main import create_app
from app.platforms.identity import PlatformIdentity, upsert_platform_user


DATABASE_URL = os.environ["DATABASE_URL"]
ADMIN_TOKEN = "test-admin-bridge"


async def add_identity(provider: str, user_id: str) -> None:
    database = Database(DATABASE_URL)
    try:
        async with database.sessions.begin() as session:
            await upsert_platform_user(
                session,
                PlatformIdentity(
                    provider=provider,
                    user_id=user_id,
                    display_name=f"Пользователь {provider}",
                    username=f"test_{user_id[-8:]}",
                ),
            )
    finally:
        await database.dispose()


async def clear_broadcasts() -> None:
    database = Database(DATABASE_URL)
    try:
        async with database.sessions.begin() as session:
            await session.execute(delete(BroadcastCampaign))
    finally:
        await database.dispose()


async def campaign_state(campaign_id: str) -> tuple[str, int, int, list[str]]:
    database = Database(DATABASE_URL)
    try:
        async with database.sessions() as session:
            campaign = await session.get(BroadcastCampaign, UUID(campaign_id))
            assert campaign is not None
            statuses = (
                await session.execute(
                    select(BroadcastRecipient.status).where(
                        BroadcastRecipient.campaign_id == campaign.id
                    )
                )
            ).scalars().all()
            return (
                campaign.status,
                campaign.sent_count,
                campaign.total_count,
                list(statuses),
            )
    finally:
        await database.dispose()


async def deliver_one(campaign_id: str) -> list[tuple[str, str]]:
    delivered: list[tuple[str, str]] = []

    async def sender(provider_user_id: str, text: str) -> None:
        delivered.append((provider_user_id, text))

    database = Database(DATABASE_URL)
    try:
        worker = BroadcastWorker(database, "max", sender)
        claimed = await worker._claim()
        assert claimed is not None
        recipient_id, provider_user_id, message = claimed
        await sender(provider_user_id, message)
        await worker._finish(recipient_id, status="sent")
    finally:
        await database.dispose()
    status, sent, total, recipients = await campaign_state(campaign_id)
    assert sent == 1
    assert total >= 1
    assert "sent" in recipients
    assert status == ("completed" if total == 1 else "running")
    return delivered


def test_admin_audience_export_and_broadcast(monkeypatch) -> None:
    monkeypatch.setenv("ADMIN_BRIDGE_TOKEN", ADMIN_TOKEN)
    suffix = uuid4().hex
    max_user_id = int(suffix[:14], 16)
    telegram_user_id = str(int(suffix[14:28], 16))
    asyncio.run(clear_broadcasts())
    asyncio.run(add_identity("telegram", telegram_user_id))
    asyncio.run(add_identity("max", str(max_user_id)))

    application = create_app(database_enabled=True, database_url=DATABASE_URL)
    with TestClient(application) as client:
        headers = {"X-Admin-Token": ADMIN_TOKEN, "X-Admin-Actor": "pytest"}

        unauthorized = client.get("/internal/admin/audience")
        assert unauthorized.status_code == 401

        overview = client.get(
            "/internal/admin/audience",
            params={"platform": "telegram", "search": telegram_user_id},
            headers=headers,
        )
        assert overview.status_code == 200, overview.text
        body = overview.json()
        assert body["stats"]["total"] >= 1
        assert body["users"]["items"][0]["provider_user_id"] == telegram_user_id
        assert body["platforms"]["max"]["total"] >= 1
        assert body["segments"]["all"] >= 1
        assert body["segments"]["active_7d"] >= 1

        exported = client.get(
            "/internal/admin/audience/export.csv",
            params={"platform": "telegram", "search": telegram_user_id},
            headers=headers,
        )
        assert exported.status_code == 200
        assert telegram_user_id in exported.content.decode("utf-8-sig")

        preview = client.post(
            "/internal/admin/audience/broadcast/preview",
            headers=headers,
            json={"platform": "max", "segment": "all", "text": "Проверка"},
        )
        assert preview.status_code == 200
        assert preview.json()["recipients"] >= 1

        queued = client.post(
            "/internal/admin/audience/broadcast",
            headers=headers,
            json={
                "platform": "max",
                "segment": "all",
                "text": f"Тестовая рассылка {suffix}",
            },
        )
        assert queued.status_code == 201, queued.text
        campaign_id = queued.json()["campaign_id"]

    delivered = asyncio.run(deliver_one(campaign_id))
    assert len(delivered) == 1
    assert delivered[0][0]
    assert delivered[0][1] == f"Тестовая рассылка {suffix}"
