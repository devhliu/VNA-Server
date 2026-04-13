"""Durable webhook event dispatcher."""
from __future__ import annotations

import hashlib
import hmac
import json
import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

import httpx
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from bids_server.config import settings
from bids_server.db.session import async_session
from bids_server.models.database import Webhook, WebhookDelivery

logger = logging.getLogger(__name__)
WEBHOOK_RETRY_DELAYS = [10, 30, 90, 270, 810, 2430]
RETRYABLE_EXCEPTIONS = (httpx.TimeoutException, httpx.NetworkError, httpx.HTTPStatusError, httpx.RequestError)


class WebhookManager:
    """Dispatches events to registered webhooks using durable delivery records."""

    async def dispatch(
        self,
        event: str,
        payload: dict,
        resource_id: Optional[str] = None,
    ) -> int:
        """Persist delivery records and attempt immediate delivery."""
        async with async_session() as db:
            result = await db.execute(
                select(Webhook).where(Webhook.active.is_(True)).order_by(Webhook.created_at.asc())
            )
            webhooks = list(result.scalars().all())
            delivery_ids: list[str] = []

            for webhook in webhooks:
                if not self._matches(webhook, event, resource_id):
                    continue
                delivery = WebhookDelivery(
                    webhook_id=webhook.webhook_id,
                    target_url=webhook.url,
                    secret=webhook.secret,
                    event=event,
                    payload={"event": event, "data": payload},
                    status="queued",
                    max_attempts=settings.webhook_max_attempts,
                    next_attempt_at=self.utcnow(),
                )
                db.add(delivery)
                await db.flush()
                delivery_ids.append(delivery.delivery_id)
            await db.commit()

        for delivery_id in delivery_ids:
            await self.send_delivery(delivery_id)
        return len(delivery_ids)

    async def list_deliveries(self, db: AsyncSession) -> list[WebhookDelivery]:
        result = await db.execute(select(WebhookDelivery).order_by(WebhookDelivery.created_at.asc()))
        return list(result.scalars().all())

    async def get_delivery(self, db: AsyncSession, delivery_id: str) -> Optional[WebhookDelivery]:
        result = await db.execute(select(WebhookDelivery).where(WebhookDelivery.delivery_id == delivery_id))
        return result.scalar_one_or_none()

    async def run_due_deliveries_once(self, db: Optional[AsyncSession] = None) -> int:
        if db is None:
            async with async_session() as session:
                count = await self.run_due_deliveries_once(session)
                await session.commit()
                return count

        now = self.utcnow()
        result = await db.execute(
            select(WebhookDelivery)
            .where(
                WebhookDelivery.status.in_(["queued", "retrying"]),
                or_(WebhookDelivery.next_attempt_at.is_(None), WebhookDelivery.next_attempt_at <= now),
            )
            .order_by(WebhookDelivery.created_at.asc())
        )
        deliveries = list(result.scalars().all())
        count = 0
        for delivery in deliveries:
            await self._send_delivery_record(db, delivery)
            count += 1
        return count

    async def send_delivery(self, delivery_id: str) -> None:
        async with async_session() as db:
            delivery = await self.get_delivery(db, delivery_id)
            if delivery is None:
                return
            await self._send_delivery_record(db, delivery)
            await db.commit()

    async def count_statuses(self, db: AsyncSession) -> dict[str, int]:
        result = await db.execute(select(WebhookDelivery.status))
        statuses = {"failed": 0, "retrying": 0, "queued": 0}
        for (status,) in result.all():
            if status in statuses:
                statuses[status] += 1
        return statuses

    async def _send_delivery_record(self, db: AsyncSession, delivery: WebhookDelivery) -> None:
        now = self.utcnow()
        delivery.attempt_count += 1
        delivery.last_attempt_at = now
        delivery.updated_at = now
        body = json.dumps(delivery.payload)
        headers = {"Content-Type": "application/json"}
        if delivery.secret:
            signature = hmac.new(
                delivery.secret.encode(),
                body.encode(),
                hashlib.sha256,
            ).hexdigest()
            headers["X-BIDSServer-Signature"] = f"sha256={signature}"

        try:
            async with httpx.AsyncClient(timeout=settings.webhook_timeout_seconds) as client:
                response = await client.post(delivery.target_url, content=body, headers=headers)
                response.raise_for_status()
            delivery.status = "completed"
            delivery.response_status = response.status_code
            delivery.error = None
            delivery.next_attempt_at = None
        except RETRYABLE_EXCEPTIONS as exc:
            status_code = getattr(getattr(exc, "response", None), "status_code", None)
            delivery.response_status = status_code
            delivery.error = str(exc)
            if delivery.attempt_count < delivery.max_attempts:
                delay = WEBHOOK_RETRY_DELAYS[delivery.attempt_count - 1]
                delivery.status = "retrying"
                delivery.next_attempt_at = now + timedelta(seconds=delay)
            else:
                delivery.status = "failed"
                delivery.next_attempt_at = None
            logger.warning("Webhook delivery %s failed: %s", delivery.delivery_id, exc)
        except Exception as exc:  # noqa: BLE001
            delivery.response_status = None
            delivery.error = str(exc)
            delivery.status = "failed"
            delivery.next_attempt_at = None
            logger.exception("Unexpected webhook failure for %s", delivery.delivery_id)
        finally:
            await db.flush()

    def _matches(self, webhook: Webhook, event: str, resource_id: Optional[str]) -> bool:
        events = webhook.events or []
        if event not in events and "*" not in events:
            return False
        filters = webhook.filters or {}
        if filters and resource_id:
            filter_resources = filters.get("resource_ids", [])
            if filter_resources and resource_id not in filter_resources:
                return False
        return True

    async def run_delivery_loop(self) -> None:
        """Persistent delivery loop — polls for due webhook deliveries."""
        import asyncio
        logger.info("Webhook delivery loop started (poll interval: %.1fs)", settings.worker_poll_interval_seconds)
        while True:
            try:
                count = await self.run_due_deliveries_once()
                if count:
                    logger.debug("Webhook delivery loop: delivered %d", count)
            except asyncio.CancelledError:
                logger.info("Webhook delivery loop shutting down")
                break
            except Exception:  # noqa: BLE001
                logger.exception("Webhook delivery loop iteration failed")
            await asyncio.sleep(settings.worker_poll_interval_seconds)

    @staticmethod
    def utcnow() -> datetime:
        return datetime.now(timezone.utc)


webhook_manager = WebhookManager()
