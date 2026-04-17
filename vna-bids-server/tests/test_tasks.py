"""Task and webhook durability tests."""
from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone

import httpx
import pytest

from bids_server.config import settings
from bids_server.core.webhook_manager import webhook_manager
from bids_server.models.database import Task, Webhook, WebhookDelivery
from bids_server.services.task_service import task_service


def assert_seconds_until(target: datetime, expected: int) -> None:
    delta = (target - datetime.now(timezone.utc)).total_seconds()
    assert expected - 2 <= delta <= expected + 2


@pytest.mark.asyncio
class TestTaskDurability:
    async def test_retryable_task_moves_to_retrying(self, db_session):
        task = await task_service.create_task(db_session, action="validate", params={"force_error": "transient"})
        claimed = await task_service.claim_next_task(db_session)
        await task_service.execute_task(db_session, claimed)
        refreshed = await task_service.get_task(db_session, task.task_id)
        assert refreshed.status == "retrying"
        assert refreshed.attempt_count == 1
        assert_seconds_until(refreshed.next_attempt_at, 5)

    async def test_non_retryable_task_fails(self, db_session):
        task = await task_service.create_task(db_session, action="validate", params={"force_error": "terminal"})
        claimed = await task_service.claim_next_task(db_session)
        await task_service.execute_task(db_session, claimed)
        refreshed = await task_service.get_task(db_session, task.task_id)
        assert refreshed.status == "failed"
        assert "terminal task failure" in refreshed.error

    async def test_retrying_task_only_claimed_when_due(self, db_session):
        task = await task_service.create_task(db_session, action="validate")
        task.status = "retrying"
        task.next_attempt_at = datetime.now(timezone.utc) + timedelta(seconds=60)
        await db_session.flush()
        claimed = await task_service.claim_next_task(db_session)
        assert claimed is None

        task.next_attempt_at = datetime.now(timezone.utc) - timedelta(seconds=1)
        await db_session.flush()
        claimed = await task_service.claim_next_task(db_session)
        assert claimed.task_id == task.task_id

    async def test_reclaim_stale_running_task(self, db_session):
        task = await task_service.create_task(db_session, action="validate")
        claimed = await task_service.claim_next_task(db_session)
        claimed.updated_at = datetime.now(timezone.utc) - timedelta(seconds=settings.stale_task_seconds + 1)
        await db_session.flush()
        reclaimed = await task_service.reclaim_stale_running(db_session)
        refreshed = await task_service.get_task(db_session, task.task_id)
        assert reclaimed == 1
        assert refreshed.status == "retrying"
        assert "stale-worker timeout" in refreshed.error

    async def test_execute_task_completes_supported_action(self, db_session):
        task = await task_service.create_task(db_session, action="validate")
        claimed = await task_service.claim_next_task(db_session)
        await task_service.execute_task(db_session, claimed)
        refreshed = await task_service.get_task(db_session, task.task_id)
        assert refreshed.status == "completed"
        assert refreshed.result["action"] == "validate"

    async def test_heartbeat_updates_timestamp_for_long_task(self, db_session, monkeypatch):
        async def slow_action(db, task):
            await asyncio.sleep(0.03)
            return {"status": "ok"}

        monkeypatch.setattr(task_service, "_execute_action", slow_action)
        monkeypatch.setattr(settings, "worker_heartbeat_seconds", 0.01)
        task = await task_service.create_task(db_session, action="validate")
        claimed = await task_service.claim_next_task(db_session)
        started_at = claimed.updated_at
        await task_service.execute_task(db_session, claimed)
        refreshed = await task_service.get_task(db_session, task.task_id)
        assert refreshed.updated_at >= started_at
        assert refreshed.status == "completed"


class _FailingAsyncClient:
    def __init__(self, *args, **kwargs):
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def post(self, *args, **kwargs):
        raise httpx.TimeoutException("timeout")


class _SuccessResponse:
    status_code = 200

    def raise_for_status(self):
        return None


class _SuccessAsyncClient:
    def __init__(self, *args, **kwargs):
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def post(self, *args, **kwargs):
        return _SuccessResponse()


@pytest.mark.asyncio
class TestWebhookDurability:
    async def test_dispatch_persists_retrying_delivery(self, db_session, monkeypatch):
        monkeypatch.setattr(httpx, "AsyncClient", _FailingAsyncClient)
        db_session.add(
            Webhook(
                url="http://example.test/hook",
                events=["resource.created"],
                secret="secret",
            )
        )
        await db_session.commit()

        created = await webhook_manager.dispatch("resource.created", {"resource_id": "res-1"})
        assert created == 1

        deliveries = await webhook_manager.list_deliveries(db_session)
        assert len(deliveries) == 1
        assert deliveries[0].status == "retrying"
        assert deliveries[0].attempt_count == 1
        assert deliveries[0].target_url == "http://example.test/hook"
        assert deliveries[0].event == "resource.created"
        assert deliveries[0].error is not None

    async def test_due_retry_delivery_is_sent(self, db_session, monkeypatch):
        monkeypatch.setattr(httpx, "AsyncClient", _SuccessAsyncClient)
        db_session.add(
            Webhook(
                webhook_id="whk-1",
                url="http://example.test/hook",
                events=["resource.created"],
                secret="secret",
            )
        )
        await db_session.flush()
        delivery = WebhookDelivery(
            webhook_id="whk-1",
            target_url="http://example.test/hook",
            event="resource.created",
            payload={"event": "resource.created", "data": {"id": "x"}},
            status="retrying",
            next_attempt_at=datetime.now(timezone.utc) - timedelta(seconds=1),
            secret="secret",
        )
        db_session.add(delivery)
        await db_session.flush()

        sent = await webhook_manager.run_due_deliveries_once(db_session)
        refreshed = await webhook_manager.get_delivery(db_session, delivery.delivery_id)
        assert sent == 1
        assert refreshed.status == "completed"
        assert refreshed.attempt_count == 1
        assert refreshed.response_status == 200

    async def test_future_retry_delivery_is_skipped(self, db_session, monkeypatch):
        monkeypatch.setattr(httpx, "AsyncClient", _SuccessAsyncClient)
        db_session.add(
            Webhook(
                webhook_id="whk-1",
                url="http://example.test/hook",
                events=["resource.created"],
            )
        )
        await db_session.flush()
        delivery = WebhookDelivery(
            webhook_id="whk-1",
            target_url="http://example.test/hook",
            event="resource.created",
            payload={"event": "resource.created", "data": {"id": "x"}},
            status="retrying",
            next_attempt_at=datetime.now(timezone.utc) + timedelta(seconds=30),
        )
        db_session.add(delivery)
        await db_session.flush()

        sent = await webhook_manager.run_due_deliveries_once(db_session)
        refreshed = await webhook_manager.get_delivery(db_session, delivery.delivery_id)
        assert sent == 0
        assert refreshed.attempt_count == 0
