import datetime
import uuid

import pytest
from redis.exceptions import ConnectionError as RedisConnectionError

from config import settings
from database.models.check_results import CheckResults
from database.models.tasks import Tasks
from schemas.enums import TaskStatus
from schemas.task_message import TaskMessage


async def test_create_task_returns_201_and_publishes_message(client, fake_redis):
    response = await client.post(
        "/api/v1/task",
        json={"urls": ["https://ya.ru", "https://google.com"]},
    )

    assert response.status_code == 201
    body = response.json()
    assert body["status"] == TaskStatus.QUEUED.value
    assert body["urls_count"] == 2
    uuid.UUID(body["task_id"])

    published = fake_redis.messages(settings.redis.stream)
    assert len(published) == 1
    message = TaskMessage.model_validate_json(published[0]["payload"])
    assert str(message.task_id) == body["task_id"]
    assert [str(url) for url in message.urls] == [
        "https://ya.ru/",
        "https://google.com/",
    ]


@pytest.mark.parametrize(
    "payload",
    [
        {"urls": []},
        {"urls": ["не-ссылка"]},
        {"urls": ["ftp://example.com"]},
        {},
    ],
)
async def test_create_task_rejects_invalid_payload(client, fake_redis, payload):
    response = await client.post("/api/v1/task", json=payload)

    assert response.status_code == 422
    assert fake_redis.messages(settings.redis.stream) == []


async def test_create_task_returns_503_when_broker_is_down(client, fake_redis, session):
    fake_redis.fail = RedisConnectionError("Error 10061 connecting to redis")

    response = await client.post("/api/v1/task", json={"urls": ["https://ya.ru"]})

    assert response.status_code == 503
    stored = (await session.execute(Tasks.__table__.select())).mappings().all()
    assert [row["status"] for row in stored] == [TaskStatus.FAILED]


async def test_get_unknown_task_returns_404(client):
    response = await client.get(f"/api/v1/task/{uuid.uuid4()}")

    assert response.status_code == 404
    assert "не найдена" in response.json()["detail"]


async def test_get_completed_task_returns_results(client, session, task_id):
    session.add(Tasks(id=task_id, status=TaskStatus.COMPLETED, total_urls=2))
    await session.commit()

    session.add_all(
        [
            CheckResults(
                task_id=task_id,
                url="https://ya.ru/",
                status_code=200,
                response_time=145.3,
                is_available=True,
                error_message=None,
                checked_at=datetime.datetime.now(datetime.timezone.utc),
            ),
            CheckResults(
                task_id=task_id,
                url="https://github.com/",
                status_code=None,
                response_time=None,
                is_available=False,
                error_message="Connection timeout",
                checked_at=datetime.datetime.now(datetime.timezone.utc),
            ),
        ]
    )
    await session.commit()

    response = await client.get(f"/api/v1/task/{task_id}")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == TaskStatus.COMPLETED.value
    assert body["total_urls"] == 2
    assert body["processed_urls"] == 2
    assert body["results"][1]["error_message"] == "Connection timeout"
    assert body["results"][1]["status_code"] is None
