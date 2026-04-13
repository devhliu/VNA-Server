"""Test configuration and fixtures."""
import asyncio
import os
import tempfile
from datetime import datetime, timedelta, timezone

# Set test env BEFORE any app imports
_test_dir = tempfile.mkdtemp()
os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///:memory:"
os.environ["BIDS_ROOT"] = _test_dir
os.environ["UPLOAD_TEMP_DIR"] = os.path.join(_test_dir, "uploads")
os.environ["ENABLE_BACKGROUND_WORKER"] = "false"

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from bids_server.db.session import get_db
from bids_server.models.database import Base, WebhookDelivery
from bids_server.services.task_service import task_service

# Test database engine (SQLite in-memory, FK disabled)
test_engine = create_async_engine(
    "sqlite+aiosqlite:///:memory:",
    echo=False,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)


@event.listens_for(test_engine.sync_engine, "connect")
def _enable_fk(dbapi_conn, record):
    dbapi_conn.cursor().execute("PRAGMA foreign_keys=ON")


test_session = async_sessionmaker(test_engine, class_=AsyncSession, expire_on_commit=False)

# Patch session module
import bids_server.db.session as session_module

session_module.engine = test_engine
session_module.async_session = test_session

import bids_server.core.webhook_manager as webhook_manager_module
import bids_server.main as main_module
import bids_server.services.task_service as task_service_module

webhook_manager_module.async_session = test_session
task_service_module.async_session = test_session
main_module.async_session = test_session
main_module.engine = test_engine

from bids_server.main import app


async def override_get_db():
    """Test DB dependency."""
    session = test_session()
    try:
        yield session
        await session.commit()
    except Exception:
        await session.rollback()
        raise
    finally:
        await session.close()


app.dependency_overrides[get_db] = override_get_db


@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture(autouse=True)
async def setup_db():
    """Create tables before each test, drop after."""
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    from bids_server.api.modalities import load_default_modalities

    session = test_session()
    try:
        task_service._last_reclaim_at = None
        await load_default_modalities(session)
        await session.commit()
    finally:
        await session.close()

    yield

    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest_asyncio.fixture
async def db_session():
    session = test_session()
    try:
        yield session
        await session.commit()
    finally:
        await session.close()


@pytest_asyncio.fixture
async def client():
    """Async HTTP test client."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest_asyncio.fixture
async def seeded_failed_delivery(db_session):
    delivery = WebhookDelivery(
        webhook_id="whk-test",
        target_url="http://example.test/hook",
        event="resource.created",
        payload={"event": "resource.created", "data": {"id": "x"}},
        status="failed",
        error="boom",
    )
    db_session.add(delivery)
    await db_session.flush()
    await db_session.commit()
    return delivery


@pytest_asyncio.fixture
async def seeded_boundary_retry_state(db_session):
    for idx in range(10):
        db_session.add(
            WebhookDelivery(
                webhook_id=f"whk-{idx}",
                target_url=f"http://example.test/{idx}",
                event="resource.created",
                payload={"event": "resource.created", "data": {"idx": idx}},
                status="retrying",
                next_attempt_at=datetime.now(timezone.utc) + timedelta(seconds=5),
            )
        )
    for idx in range(5):
        await task_service.create_task(db_session, action=f"test-{idx}")
    tasks = await task_service.list_tasks(db_session, limit=10)
    for task in tasks[:5]:
        task.status = "retrying"
        task.next_attempt_at = datetime.now(timezone.utc) + timedelta(seconds=5)
    await db_session.flush()
    await db_session.commit()
    return True


@pytest_asyncio.fixture
async def seeded_retry_backlog(db_session):
    for idx in range(11):
        db_session.add(
            WebhookDelivery(
                webhook_id=f"whk-r-{idx}",
                target_url=f"http://example.test/retry/{idx}",
                event="resource.created",
                payload={"event": "resource.created", "data": {"idx": idx}},
                status="retrying",
                next_attempt_at=datetime.now(timezone.utc) + timedelta(seconds=5),
            )
        )
    for idx in range(6):
        task = await task_service.create_task(db_session, action=f"retry-{idx}")
        task.status = "retrying"
        task.next_attempt_at = datetime.now(timezone.utc) + timedelta(seconds=5)
    await db_session.flush()
    await db_session.commit()
    return True
