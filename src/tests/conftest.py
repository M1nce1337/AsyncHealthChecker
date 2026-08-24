import uuid
from typing import AsyncGenerator

import asyncpg
import httpx
import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from config import settings
from database.db_helper import db_helper
from database.models.base import Base
from broker.redis_helper import redis_helper
from main import app
import services.check_service as check_service
import worker.__main__ as worker_main
from monitoring.counters import record_task_processed

TEST_DB_NAME = "async_health_checker_test"


def _dsn_without_database() -> str:
    """Отрезает имя базы от рабочего DSN, оставляя пользователя, хост и порт."""
    return str(settings.db.url).rsplit("/", 1)[0]


def _admin_dsn() -> str:
    return _dsn_without_database().replace("postgresql+asyncpg://", "postgresql://") + "/postgres"


def _test_dsn() -> str:
    return f"{_dsn_without_database()}/{TEST_DB_NAME}"


@pytest.fixture(scope="session")
async def engine():
    admin = await asyncpg.connect(_admin_dsn())
    await admin.execute(f'DROP DATABASE IF EXISTS "{TEST_DB_NAME}"')
    await admin.execute(f'CREATE DATABASE "{TEST_DB_NAME}"')
    await admin.close()

    engine = create_async_engine(_test_dsn())
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()

    admin = await asyncpg.connect(_admin_dsn())
    await admin.execute(f'DROP DATABASE IF EXISTS "{TEST_DB_NAME}"')
    await admin.close()


@pytest.fixture(autouse=True)
async def clean_tables(engine):
    """Каждый тест начинается с пустых таблиц."""
    yield
    async with engine.begin() as conn:
        await conn.execute(text("TRUNCATE tasks, check_results RESTART IDENTITY CASCADE"))


@pytest.fixture
async def session(engine) -> AsyncGenerator[AsyncSession, None]:
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        yield session
        await session.rollback()


@pytest.fixture
def session_factory(engine) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(engine, expire_on_commit=False)


class FakeRedis:
    """Минимальный двойник Redis: запоминает всё, что в него опубликовали."""

    def __init__(self, fail: Exception | None = None):
        self.fail = fail
        self.streams: dict[str, list[tuple[str, dict[str, str]]]] = {}
        self.acked: list[str] = []

    async def xadd(self, name, fields, maxlen=None, approximate=None):
        if self.fail is not None:
            raise self.fail
        message_id = f"{len(self.streams.get(name, []))}-0"
        self.streams.setdefault(name, []).append((message_id, dict(fields)))
        return message_id

    async def xack(self, stream, group, message_id):
        self.acked.append(message_id)
        return 1

    def messages(self, stream: str) -> list[dict[str, str]]:
        return [fields for _, fields in self.streams.get(stream, [])]


    async def incr(self, key):
        return 1

    async def incrby(self, key, amount):
        return amount

    async def set(self, key, value, ex=None):
        return True


@pytest.fixture
def fake_redis() -> FakeRedis:
    return FakeRedis()


@pytest.fixture(autouse=True)
def stub_metrics(monkeypatch):
    """Счётчики метрик не должны требовать живого Redis в тестах."""

    async def noop(*args, **kwargs):
        return None

    monkeypatch.setattr(check_service, "record_task_processed", noop)
    monkeypatch.setattr(check_service, "record_task_failed", noop)
    monkeypatch.setattr(worker_main, "heartbeat", noop)


@pytest.fixture
async def client(engine, fake_redis) -> AsyncGenerator[httpx.AsyncClient, None]:

    factory = async_sessionmaker(engine, expire_on_commit=False)

    async def override_session():
        async with factory() as session:
            yield session

    async def override_redis():
        return fake_redis

    app.dependency_overrides[db_helper.session_getter] = override_session
    app.dependency_overrides[redis_helper.client_getter] = override_redis

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac

    app.dependency_overrides.clear()


@pytest.fixture
def task_id() -> uuid.UUID:
    return uuid.uuid4()
