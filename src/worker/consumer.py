import structlog
from redis.asyncio import Redis
from redis.exceptions import ResponseError

from config import settings

log = structlog.get_logger(__name__)

Message = tuple[str, dict[str, str]]


class StreamConsumer:
    """Чтение задач из Redis Stream через consumer group."""

    def __init__(self, redis: Redis, consumer_name: str):
        self.redis = redis
        self.consumer_name = consumer_name
        self.stream = settings.redis.stream
        self.group = settings.redis.group

    async def ensure_group(self) -> None:
        try:
            await self.redis.xgroup_create(
                name=self.stream,
                groupname=self.group,
                id="0",
                mkstream=True,
            )
            log.info("consumer group created", stream=self.stream, group=self.group)
        except ResponseError as exc:
            if "BUSYGROUP" not in str(exc):
                raise
            log.info("consumer group already exists", stream=self.stream, group=self.group)

    async def read(self) -> list[Message]:
        response = await self.redis.xreadgroup(
            groupname=self.group,
            consumername=self.consumer_name,
            streams={self.stream: ">"},
            count=settings.redis.batch_size,
            block=settings.redis.block_ms,
        )
        if not response:
            return []
        _, messages = response[0]
        return messages

    async def claim_stale(self) -> list[Message]:
        _, messages, _ = await self.redis.xautoclaim(
            name=self.stream,
            groupname=self.group,
            consumername=self.consumer_name,
            min_idle_time=settings.worker.claim_min_idle_ms,
            count=settings.redis.batch_size,
        )
        if messages:
            log.warning("stale messages claimed", count=len(messages))
        return messages

    async def ack(self, message_id: str) -> None:
        await self.redis.xack(self.stream, self.group, message_id)

    async def pending_count(self) -> int:
        summary = await self.redis.xpending(self.stream, self.group)
        return summary.get("pending", 0)
