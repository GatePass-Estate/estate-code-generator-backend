import logging
from contextlib import asynccontextmanager
from typing import AsyncGenerator

import redis.asyncio as redis
from redis.exceptions import RedisError

from app.core.config import settings

logger = logging.getLogger(__name__)


class AsyncRedisClient:
    def __init__(self) -> None:
        self._client: redis.Redis | None = None

    async def init(self) -> None:
        self._client = redis.from_url(
            settings.REDIS_URL, decode_responses=True
        )

    async def close(self) -> None:
        if self._client:
            await self._client.close()

    @asynccontextmanager
    async def connection(self) -> AsyncGenerator[redis.Redis, None]:
        if not self._client:
            await self.init()

        if not await self._ensure_connection():
            await self.close()
            await self.init()

        try:
            yield self._client
        except Exception as e:
            logger.exception("Error in Redis connection: %s", str(e))
            raise

    async def _ensure_connection(self) -> bool:
        try:
            # Use the PING command to verify connection.
            await self._client.ping()
            return True
        except RedisError:
            logger.exception("Error connecting to Redis")
            return False

    @asynccontextmanager
    async def connection_scope(self) -> AsyncGenerator[redis.Redis, None]:
        async with self.connection() as conn:
            yield conn


redis_client = AsyncRedisClient()


async def get_redis_connection() -> AsyncGenerator[redis.Redis, None]:
    """
    Get an asynchronous Redis connection.

    Returns:
        AsyncGenerator[redis.Redis, None]: An async Redis connection.
    """
    async with redis_client.connection() as conn:
        yield conn
