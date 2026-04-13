"""Webhook subscription service - manage event subscriptions for sub-server callbacks."""

from __future__ import annotations

import asyncio
import hashlib
import json
import hmac
import logging
import secrets
from datetime import datetime, timezone
from typing import Any, Callable, Coroutine

import httpx
from sqlalchemy import delete, select, func
from sqlalchemy.ext.asyncio import AsyncSession

from vna_main.models.database import WebhookDeliveryLog, WebhookSubscription

logger = logging.getLogger(__name__)


class WebhookService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create_subscription(
        self,
        url: str,
        events: list[str],
        *,
        secret: str | None = None,
        description: str | None = None,
        enabled: bool = True,
    ) -> WebhookSubscription:
        sub = WebhookSubscription(
            url=url,
            events=events,
            secret=secret or secrets.token_urlsafe(32),
            description=description,
            enabled=enabled,
        )
        self.session.add(sub)
        await self.session.flush()
        return sub

    async def list_subscriptions(
        self,
        *,
        event: str | None = None,
        enabled: bool | None = None,
        offset: int = 0,
        limit: int = 50,
    ) -> tuple[list[WebhookSubscription], int]:
        stmt = select(WebhookSubscription)
        count_stmt = select(func.count()).select_from(WebhookSubscription)
        if event:
            stmt = stmt.where(WebhookSubscription.events.contains([event]))
            count_stmt = count_stmt.where(WebhookSubscription.events.contains([event]))
        if enabled is not None:
            stmt = stmt.where(WebhookSubscription.enabled == enabled)
            count_stmt = count_stmt.where(WebhookSubscription.enabled == enabled)
        
        # Get total count
        total_result = await self.session.execute(count_stmt)
        total = total_result.scalar() or 0
        
        # Get paginated results
        stmt = stmt.offset(offset).limit(limit).order_by(WebhookSubscription.created_at.desc())
        result = await self.session.execute(stmt)
        subs = list(result.scalars().all())
        
        return subs, total

    async def get_subscription(self, sub_id: int) -> WebhookSubscription | None:
        return await self.session.get(WebhookSubscription, sub_id)

    async def update_subscription(
        self,
        sub_id: int,
        *,
        url: str | None = None,
        events: list[str] | None = None,
        secret: str | None = None,
        description: str | None = None,
        enabled: bool | None = None,
    ) -> WebhookSubscription | None:
        sub = await self.session.get(WebhookSubscription, sub_id)
        if not sub:
            return None
        if url is not None:
            sub.url = url
        if events is not None:
            sub.events = events
        if secret is not None:
            sub.secret = secret
        if description is not None:
            sub.description = description
        if enabled is not None:
            sub.enabled = enabled
        await self.session.flush()
        return sub

    async def delete_subscription(self, sub_id: int) -> bool:
        sub = await self.session.get(WebhookSubscription, sub_id)
        if not sub:
            return False
        await self.session.delete(sub)
        await self.session.flush()
        return True

    async def get_subscription_stats(self) -> dict[str, Any]:
        total = (
            await self.session.execute(
                select(func.count()).select_from(WebhookSubscription)
            )
        ).scalar() or 0
        enabled = (
            await self.session.execute(
                select(func.count())
                .select_from(WebhookSubscription)
                .where(
                    WebhookSubscription.enabled == True  # noqa: E712
                )
            )
        ).scalar() or 0

        all_subs = await self.list_subscriptions()
        event_counts: dict[str, int] = {}
        for sub in all_subs:
            for evt in sub.events:
                event_counts[evt] = event_counts.get(evt, 0) + 1

        return {
            "total": total,
            "enabled": enabled,
            "disabled": total - enabled,
            "event_counts": event_counts,
        }


class WebhookDelivery:
    def __init__(
        self, session: AsyncSession, max_retries: int = 3, retry_delay: float = 2.0
    ):
        self.session = session
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self._queue: asyncio.Queue | None = None
        self._worker_task: asyncio.Task | None = None

    @staticmethod
    def _sign_payload(payload: str, secret: str) -> str:
        return hmac.new(
            secret.encode(),
            payload.encode(),
            hashlib.sha256,
        ).hexdigest()

    async def deliver(
        self,
        sub: WebhookSubscription,
        event_type: str,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        import uuid

        delivery_id = uuid.uuid4().hex[:12]
        payload_json = json.dumps(payload)
        signature = self._sign_payload(payload_json, sub.secret)

        headers = {
            "Content-Type": "application/json",
            "X-Webhook-Event": event_type,
            "X-Webhook-Delivery": delivery_id,
            "X-Webhook-Signature": f"sha256={signature}",
        }

        last_error: str | None = None
        for attempt in range(self.max_retries):
            try:
                from vna_main.services.http_client import get_http_client
                client = get_http_client()
                resp = await client.post(
                    sub.url,
                    content=payload_json,
                    headers=headers,
                )
                    success = 200 <= resp.status_code < 300
                    return {
                        "delivery_id": delivery_id,
                        "status_code": resp.status_code,
                        "success": success,
                        "attempt": attempt + 1,
                        "error": None
                        if success
                        else f"HTTP {resp.status_code}: {resp.text[:200]}",
                    }
            except (httpx.HTTPError, httpx.TimeoutException, OSError, ValueError) as e:
                logger.error("Webhook delivery attempt %d failed for %s: %s", attempt + 1, sub.url, e, exc_info=True)
                last_error = str(e)
                if attempt < self.max_retries - 1:
                    await asyncio.sleep(self.retry_delay * (attempt + 1))

        return {
            "delivery_id": delivery_id,
            "status_code": None,
            "success": False,
            "attempt": self.max_retries,
            "error": last_error,
        }

    async def dispatch(
        self, event_type: str, payload: dict[str, Any]
    ) -> list[dict[str, Any]]:
        from vna_main.models.database import WebhookDeliveryLog

        subs = await self.session.execute(
            select(WebhookSubscription).where(
                WebhookSubscription.enabled == True,  # noqa: E712
                WebhookSubscription.events.contains([event_type]),
            )
        )
        subs = list(subs.scalars().all())
        if not subs:
            return []

        results = []
        for sub in subs:
            result = await self.deliver(sub, event_type, payload)
            log = WebhookDeliveryLog(
                subscription_id=sub.id,
                event_type=event_type,
                delivery_id=result["delivery_id"],
                payload=payload,
                response_status=result.get("status_code"),
                success=result["success"],
                error=result.get("error"),
                attempt_count=result["attempt"],
            )
            self.session.add(log)
            results.append(result)

        await self.session.flush()
        return results

    async def get_delivery_logs(
        self,
        *,
        subscription_id: int | None = None,
        event_type: str | None = None,
        limit: int = 50,
    ) -> list[WebhookDeliveryLog]:
        stmt = select(WebhookDeliveryLog)
        if subscription_id:
            stmt = stmt.where(WebhookDeliveryLog.subscription_id == subscription_id)
        if event_type:
            stmt = stmt.where(WebhookDeliveryLog.event_type == event_type)
        stmt = stmt.order_by(WebhookDeliveryLog.created_at.desc()).limit(limit)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())
