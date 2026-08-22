import structlog
from redis.asyncio import Redis

from config import settings
from schemas.task_message import TaskMessage

log = structlog.get_logger(__name__)


async def publish_task(redis: Redis, message: TaskMessage) -> bytes | str:
    message_id = await redis.xadd(
        name=settings.redis.stream,
        fields={"payload": message.model_dump_json()},
        maxlen=settings.redis.stream_maxlen,
        approximate=True,
    )
    log.info(
        "task published",
        stream=settings.redis.stream,
        message_id=message_id,
        attempt=message.attempt,
    )
    return message_id


async def republish_task(redis: Redis, message: TaskMessage) -> bytes | str:
    """Возвращает задачу в очередь со следующим номером попытки."""
    return await publish_task(
        redis,
        message.model_copy(update={"attempt": message.attempt + 1}),
    )


async def publish_to_dlq(redis: Redis, payload: str, reason: str) -> bytes | str:
    message_id = await redis.xadd(
        name=settings.redis.dlq_stream,
        fields={"payload": payload, "reason": reason},
        maxlen=settings.redis.stream_maxlen,
        approximate=True,
    )
    log.warning(
        "message moved to dead letter queue",
        stream=settings.redis.dlq_stream,
        message_id=message_id,
        reason=reason,
    )
    return message_id
