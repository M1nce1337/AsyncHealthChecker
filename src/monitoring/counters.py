import structlog
from redis.exceptions import RedisError

from broker.redis_helper import redis_helper
from config import settings
from monitoring.keys import (
    heartbeat_key,
    tasks_failed_key,
    tasks_processed_key,
    urls_checked_key,
)

log = structlog.get_logger(__name__)


async def record_task_processed(*, available: int, unavailable: int) -> None:
    """Инкрементирует счётчики после успешной обработки задачи."""
    try:
        async with redis_helper.client.pipeline(transaction=False) as pipe:
            pipe.incr(tasks_processed_key())
            if available:
                pipe.incrby(urls_checked_key("available"), available)
            if unavailable:
                pipe.incrby(urls_checked_key("unavailable"), unavailable)
            await pipe.execute()
    except RedisError as exc:
        log.warning("metrics update failed", error=str(exc))


async def record_task_failed() -> None:
    try:
        await redis_helper.client.incr(tasks_failed_key())
    except RedisError as exc:
        log.warning("metrics update failed", error=str(exc))


async def heartbeat(consumer_name: str) -> None:
    """Отмечает воркер живым; ключ сам истечёт, если воркер умрёт."""
    try:
        await redis_helper.client.set(
            heartbeat_key(consumer_name),
            "1",
            ex=settings.worker.heartbeat_ttl_s,
        )
    except RedisError as exc:
        log.warning("heartbeat failed", error=str(exc))
