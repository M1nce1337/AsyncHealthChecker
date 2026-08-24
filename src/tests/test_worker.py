import asyncio
import datetime
import uuid

import httpx
import pytest
from sqlalchemy import select

from config import settings
from database.models.check_results import CheckResults
from database.models.tasks import Tasks
from schemas.enums import TaskStatus
from schemas.task_message import TaskMessage
from services.check_service import process_task
from services.url_checker import check_url
from worker.__main__ import handle_message


class FakeConsumer:
    """Двойник StreamConsumer: фиксирует подтверждения."""

    def __init__(self):
        self.acked: list[str] = []

    async def ack(self, message_id: str) -> None:
        self.acked.append(message_id)


def make_client(handler) -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


async def seed_task(session_factory, task_id: uuid.UUID, total_urls: int) -> None:
    async with session_factory() as session:
        session.add(
            Tasks(id=task_id, status=TaskStatus.QUEUED, total_urls=total_urls)
        )
        await session.commit()


async def test_worker_saves_results_and_completes_task(session_factory, task_id):
    await seed_task(session_factory, task_id, total_urls=2)

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.host == "ok.example":
            return httpx.Response(200)
        return httpx.Response(503)

    message = TaskMessage(
        task_id=task_id,
        urls=["https://ok.example", "https://bad.example"],
        created_at=datetime.datetime.now(datetime.timezone.utc),
    )

    async with make_client(handler) as client:
        await process_task(
            message=message,
            session_factory=session_factory,
            http_client=client,
            semaphore=asyncio.Semaphore(5),
        )

    async with session_factory() as session:
        task = await session.get(Tasks, task_id)
        rows = (
            await session.scalars(
                select(CheckResults).where(CheckResults.task_id == task_id)
            )
        ).all()

    assert task.status is TaskStatus.COMPLETED
    assert len(rows) == 2
    by_url = {row.url: row for row in rows}
    assert by_url["https://ok.example/"].is_available is True
    assert by_url["https://ok.example/"].status_code == 200
    assert by_url["https://bad.example/"].is_available is False
    assert by_url["https://bad.example/"].status_code == 503


async def test_timeout_is_recorded_without_raising():
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectTimeout("timed out")

    async with make_client(handler) as client:
        outcome = await check_url(client, "https://slow.example", asyncio.Semaphore(1))

    assert outcome.is_available is False
    assert outcome.status_code is None
    assert outcome.response_time is None
    assert outcome.error_message == "Connection timeout"


async def test_repeated_delivery_does_not_duplicate_results(session_factory, task_id):
    await seed_task(session_factory, task_id, total_urls=1)

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200)

    message = TaskMessage(
        task_id=task_id,
        urls=["https://ok.example"],
        created_at=datetime.datetime.now(datetime.timezone.utc),
    )

    async with make_client(handler) as client:
        await process_task(
            message=message,
            session_factory=session_factory,
            http_client=client,
            semaphore=asyncio.Semaphore(1),
        )
        await process_task(
            message=message,
            session_factory=session_factory,
            http_client=client,
            semaphore=asyncio.Semaphore(1),
        )

    async with session_factory() as session:
        rows = (
            await session.scalars(
                select(CheckResults).where(CheckResults.task_id == task_id)
            )
        ).all()

    assert len(rows) == 1


async def test_malformed_message_goes_to_dlq_and_is_acked(monkeypatch, fake_redis):
    from broker.redis_helper import redis_helper

    monkeypatch.setattr(redis_helper, "client", fake_redis)

    consumer = FakeConsumer()
    async with make_client(lambda request: httpx.Response(200)) as client:
        await handle_message(
            "1-0",
            {"payload": "{это не json"},
            consumer=consumer,
            http_client=client,
            semaphore=asyncio.Semaphore(1),
        )

    assert consumer.acked == ["1-0"]
    dlq = fake_redis.messages(settings.redis.dlq_stream)
    assert len(dlq) == 1
    assert dlq[0]["payload"] == "{это не json"
    assert fake_redis.messages(settings.redis.stream) == []
