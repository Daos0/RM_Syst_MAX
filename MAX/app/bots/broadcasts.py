from __future__ import annotations

import asyncio
import logging
import os
from collections.abc import Awaitable, Callable
from datetime import datetime, timezone

from sqlalchemy import func, select

from app.db.models import BroadcastCampaign, BroadcastRecipient
from app.db.session import Database


logger = logging.getLogger(__name__)
Sender = Callable[[str, str], Awaitable[None]]


class BroadcastRetry(RuntimeError):
    def __init__(self, message: str, *, delay: float = 2.0) -> None:
        super().__init__(message)
        self.delay = max(0.2, delay)


class BroadcastPermanentError(RuntimeError):
    pass


class BroadcastWorker:
    def __init__(self, database: Database, provider: str, sender: Sender) -> None:
        self.database = database
        self.provider = provider
        self.sender = sender
        self.idle_delay = float(os.getenv("BROADCAST_IDLE_SECONDS", "1.0"))
        self.send_delay = float(os.getenv("BROADCAST_SEND_DELAY_SECONDS", "0.12"))

    async def _claim(self) -> tuple[int, str, str] | None:
        async with self.database.sessions.begin() as session:
            row = (
                await session.execute(
                    select(BroadcastRecipient, BroadcastCampaign)
                    .join(
                        BroadcastCampaign,
                        BroadcastCampaign.id == BroadcastRecipient.campaign_id,
                    )
                    .where(
                        BroadcastRecipient.status == "queued",
                        BroadcastCampaign.provider == self.provider,
                        BroadcastCampaign.status.in_(["queued", "running"]),
                    )
                    .order_by(BroadcastRecipient.id)
                    .limit(1)
                    .with_for_update(skip_locked=True)
                )
            ).one_or_none()
            if row is None:
                return None
            recipient, campaign = row
            now = datetime.now(timezone.utc)
            recipient.status = "sending"
            recipient.attempts += 1
            if campaign.status == "queued":
                campaign.status = "running"
                campaign.started_at = now
            await session.flush()
            return recipient.id, recipient.provider_user_id, campaign.message_text

    async def _finish(
        self,
        recipient_id: int,
        *,
        status: str,
        error: str | None = None,
    ) -> None:
        async with self.database.sessions.begin() as session:
            recipient = await session.get(
                BroadcastRecipient,
                recipient_id,
                with_for_update=True,
            )
            if recipient is None or recipient.status != "sending":
                return
            campaign = await session.get(
                BroadcastCampaign,
                recipient.campaign_id,
                with_for_update=True,
            )
            if campaign is None:
                return
            recipient.status = status
            recipient.last_error = (error or "")[:1000] or None
            if status == "sent":
                recipient.sent_at = datetime.now(timezone.utc)
                campaign.sent_count += 1
            elif status == "failed":
                campaign.failed_count += 1
            remaining = int(
                await session.scalar(
                    select(func.count(BroadcastRecipient.id)).where(
                        BroadcastRecipient.campaign_id == campaign.id,
                        BroadcastRecipient.status.in_(["queued", "sending"]),
                    )
                )
                or 0
            )
            if remaining == 0:
                campaign.status = "completed"
                campaign.completed_at = datetime.now(timezone.utc)

    async def _retry(self, recipient_id: int, error: str) -> None:
        async with self.database.sessions.begin() as session:
            recipient = await session.get(
                BroadcastRecipient,
                recipient_id,
                with_for_update=True,
            )
            if recipient is None or recipient.status != "sending":
                return
            if recipient.attempts >= 3:
                campaign = await session.get(
                    BroadcastCampaign,
                    recipient.campaign_id,
                    with_for_update=True,
                )
                recipient.status = "failed"
                recipient.last_error = error[:1000]
                if campaign is not None:
                    campaign.failed_count += 1
                    await session.flush()
                    remaining = int(
                        await session.scalar(
                            select(func.count(BroadcastRecipient.id)).where(
                                BroadcastRecipient.campaign_id == campaign.id,
                                BroadcastRecipient.status.in_(["queued", "sending"]),
                            )
                        )
                        or 0
                    )
                    if remaining == 0:
                        campaign.status = "completed"
                        campaign.completed_at = datetime.now(timezone.utc)
                return
            recipient.status = "queued"
            recipient.last_error = error[:1000]

    async def run(self) -> None:
        logger.info("Broadcast worker started provider=%s", self.provider)
        while True:
            claimed = await self._claim()
            if claimed is None:
                await asyncio.sleep(self.idle_delay)
                continue
            recipient_id, provider_user_id, message = claimed
            try:
                await self.sender(provider_user_id, message)
            except BroadcastRetry as exc:
                await self._retry(recipient_id, str(exc))
                await asyncio.sleep(exc.delay)
            except BroadcastPermanentError as exc:
                await self._finish(recipient_id, status="failed", error=str(exc))
            except asyncio.CancelledError:
                await self._retry(recipient_id, "worker_stopped")
                raise
            except Exception as exc:  # noqa: BLE001
                logger.exception("Unexpected broadcast error provider=%s", self.provider)
                await self._retry(recipient_id, str(exc))
            else:
                await self._finish(recipient_id, status="sent")
                await asyncio.sleep(self.send_delay)
