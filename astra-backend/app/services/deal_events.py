import asyncio
import json
import logging
from contextlib import asynccontextmanager, suppress
from typing import Any

from redis.asyncio import Redis

from app.core.config import settings
from app.realtime.deals_ws import manager

logger = logging.getLogger(__name__)


class DealLockTimeout(RuntimeError):
    pass


class DealEventBus:
    """Redis fan-out with an in-process fallback for local development."""

    def __init__(self) -> None:
        self._redis: Redis | None = None
        self._listener_task: asyncio.Task[None] | None = None
        self._local_locks: dict[str, asyncio.Lock] = {}

    @property
    def redis_connected(self) -> bool:
        return self._redis is not None

    async def start(self) -> None:
        client = Redis.from_url(settings.REDIS_URL, decode_responses=True, socket_connect_timeout=1)
        try:
            await client.ping()
        except Exception as error:
            await client.aclose()
            logger.warning("Redis unavailable; Deals events use local WebSocket fan-out: %s", error)
            return
        self._redis = client
        self._listener_task = asyncio.create_task(self._listen(), name="deal-redis-subscriber")

    async def stop(self) -> None:
        if self._listener_task:
            self._listener_task.cancel()
            with suppress(asyncio.CancelledError):
                await self._listener_task
        if self._redis:
            await self._redis.aclose()
        self._redis = None

    async def publish(self, event: dict[str, Any]) -> None:
        if self._redis is None:
            await manager.broadcast(event)
            return
        try:
            await self._redis.publish(settings.DEAL_EVENT_CHANNEL, json.dumps(event, default=str))
        except Exception as error:
            logger.error("Redis publish failed; broadcasting locally: %s", error)
            await manager.broadcast(event)

    @asynccontextmanager
    async def reservation_lock(self, deal_id: str):
        lock_name = f"astra:deal-reservation:{deal_id}"
        if self._redis is None:
            lock = self._local_locks.setdefault(lock_name, asyncio.Lock())
            try:
                await asyncio.wait_for(lock.acquire(), timeout=3)
            except TimeoutError as error:
                raise DealLockTimeout("Another checkout is reserving this deal") from error
            try:
                yield
            finally:
                lock.release()
            return

        redis_lock = self._redis.lock(lock_name, timeout=10, blocking_timeout=3)
        acquired = await redis_lock.acquire()
        if not acquired:
            raise DealLockTimeout("Another checkout is reserving this deal")
        try:
            yield
        finally:
            with suppress(Exception):
                await redis_lock.release()

    async def _listen(self) -> None:
        assert self._redis is not None
        pubsub = self._redis.pubsub()
        await pubsub.subscribe(settings.DEAL_EVENT_CHANNEL)
        try:
            async for message in pubsub.listen():
                if message.get("type") != "message":
                    continue
                try:
                    event = json.loads(message["data"])
                except (TypeError, json.JSONDecodeError):
                    logger.warning("Discarding malformed Deals event: %r", message.get("data"))
                    continue
                await manager.broadcast(event)
        finally:
            await pubsub.unsubscribe(settings.DEAL_EVENT_CHANNEL)
            await pubsub.aclose()


deal_event_bus = DealEventBus()
