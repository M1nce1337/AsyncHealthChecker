import asyncio

import structlog
from fastapi import FastAPI
from prometheus_client import Gauge
from prometheus_fastapi_instrumentator import Instrumentator
from redis.asyncio import Redis
from redis.exceptions import RedisError, ResponseError

from config import settings
from monitoring.keys import (
    heartbeat_pattern,
    tasks_failed_key,
    tasks_processed_key,
    urls_checked_key,
)

log = structlog.get_logger(__name__)

TASKS_PROCESSED = Gauge(
    "tasks_processed_total",
    "Количество успешно обработанных задач",
)
TASKS_FAILED = Gauge(
    "tasks_failed_total",
    "Количество задач, завершившихся ошибкой",
)
URLS_CHECKED = Gauge(
    "urls_checked_total",
    "Количество проверенных URL",
    labelnames=("status",),
)
ACTIVE_WORKERS = Gauge(
    "active_workers",
    "Количество живых воркеров",
)
QUEUE_SIZE = Gauge(
    "queue_size",
    "Количество сообщений в очереди задач",
)


def setup_metrics(app: FastAPI) -> None:
    Instrumentator().instrument(app).expose(
        app,
        endpoint="/metrics",
        include_in_schema=False,
    )


async def _queue_backlog(redis: Redis) -> int:
    """Необработанный остаток очереди: недоставленные + неподтверждённые."""
    try:
        groups = await redis.xinfo_groups(settings.redis.stream)

    except ResponseError:
        return 0

    for group in groups:
        if group["name"] == settings.redis.group:
            return int(group.get("lag") or 0) + int(group.get("pending") or 0)

    return 0


async def refresh_metrics(redis: Redis) -> None:
    """Переносит счётчики из Redis в реестр Prometheus."""
    QUEUE_SIZE.set(await _queue_backlog(redis))

    alive = 0

    async for _ in redis.scan_iter(match=heartbeat_pattern(), count=100):
        alive += 1

    ACTIVE_WORKERS.set(alive)

    processed, failed, available, unavailable = await redis.mget(
        tasks_processed_key(),
        tasks_failed_key(),
        urls_checked_key("available"),
        urls_checked_key("unavailable"),
    )
    TASKS_PROCESSED.set(int(processed or 0))
    TASKS_FAILED.set(int(failed or 0))
    URLS_CHECKED.labels(status="available").set(int(available or 0))
    URLS_CHECKED.labels(status="unavailable").set(int(unavailable or 0))


async def metrics_refresher(redis: Redis) -> None:
    """Фоновая задача: обновляет метрики, пока приложение живо."""
    while True:
        try:
            await refresh_metrics(redis)

        except RedisError as exc:
            log.warning("metrics refresh failed", error=str(exc))

        except asyncio.CancelledError:
            raise

        except Exception:
            log.exception("metrics refresh crashed")

        await asyncio.sleep(settings.metrics.refresh_interval_s)