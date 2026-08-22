from redis.asyncio import ConnectionPool, Redis

from config import settings


class RedisHelper:
    def __init__(
        self,
        url: str,
        max_connections: int = 10,
        socket_timeout: float = 30.0,
    ):
        self.pool: ConnectionPool = ConnectionPool.from_url(
            url=url,
            max_connections=max_connections,
            socket_timeout=socket_timeout,
            decode_responses=True,
        )
        self.client: Redis = Redis(connection_pool=self.pool)

    async def ping(self) -> None:
        await self.client.ping()

    async def close(self) -> None:
        await self.client.aclose()
        await self.pool.disconnect()

    async def client_getter(self) -> Redis:
        return self.client


redis_helper = RedisHelper(
    url=str(settings.redis.url),
    max_connections=settings.redis.max_connections,
    socket_timeout=settings.redis.socket_timeout,
)
