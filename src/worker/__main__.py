import asyncio
import os
import signal
import socket
import time

import httpx
import structlog
from pydantic import ValidationError
from redis.exceptions import RedisError

from broker.producer import publish_to_dlq, republish_task
from broker.redis_helper import redis_helper
from config import settings
from database.db_helper import db_helper
from logging_setup.logging_config import setup_logging
from monitoring.counters import heartbeat
from schemas.task_message import TaskMessage
from services.check_service import mark_failed, process_task
from worker.consumer import Message, StreamConsumer

log = structlog.get_logger("worker")


def install_signal_handlers(stop_event: asyncio.Event) -> None:
    """Graceful shutdown по SIGTERM"""
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        try:
            loop.add_signal_handler(sig, stop_event.set)
        except NotImplementedError:
            signal.signal(sig, lambda *_: stop_event.set())


async def handle_message(
    message_id: str,
    fields: dict[str, str],
    *,
    consumer: StreamConsumer,
    http_client: httpx.AsyncClient,
    semaphore: asyncio.Semaphore,
) -> None:
    payload = fields.get("payload", "")

    try:
        message = TaskMessage.model_validate_json(payload)
    except ValidationError as exc:
        log.error("malformed message", message_id=message_id, errors=exc.error_count())
        await publish_to_dlq(redis_helper.client, payload, reason=str(exc))
        await consumer.ack(message_id)
        return

    structlog.contextvars.bind_contextvars(task_id=str(message.task_id))
    try:
        await process_task(
            message=message,
            session_factory=db_helper.session_factory,
            http_client=http_client,
            semaphore=semaphore,
        )
        await consumer.ack(message_id)

    except Exception as exc:
        log.exception("task processing failed", message_id=message_id)
        attempts_left = settings.worker.max_attempts - (message.attempt + 1)
        if attempts_left > 0:
            await republish_task(redis_helper.client, message)
        else:
            await mark_failed(
                task_id=message.task_id,
                session_factory=db_helper.session_factory,
            )
            await publish_to_dlq(
                redis_helper.client,
                payload,
                reason=f"attempts exhausted: {type(exc).__name__}: {exc}",
            )
        await consumer.ack(message_id)
    finally:
        structlog.contextvars.unbind_contextvars("task_id")


async def run_worker(stop_event: asyncio.Event | None = None) -> None:
    setup_logging()

    consumer_name = f"{socket.gethostname()}:{os.getpid()}"
    consumer = StreamConsumer(redis_helper.client, consumer_name)

    await redis_helper.ping()
    await consumer.ensure_group()

    if stop_event is None:
        stop_event = asyncio.Event()
        install_signal_handlers(stop_event)

    semaphore = asyncio.Semaphore(settings.worker.concurrency)
    last_claim = 0.0

    log.info(
        "worker started",
        consumer=consumer_name,
        stream=settings.redis.stream,
        group=settings.redis.group,
        concurrency=settings.worker.concurrency,
    )

    try:
        async with httpx.AsyncClient(
            timeout=settings.worker.request_timeout,
            follow_redirects=True,
        ) as http_client:
            while not stop_event.is_set():
                batch: list[Message] = []
                await heartbeat(consumer_name)

                try:
                    if time.monotonic() - last_claim > settings.worker.claim_interval_s:
                        last_claim = time.monotonic()
                        batch.extend(await consumer.claim_stale())

                    batch.extend(await consumer.read())
                except RedisError as exc:
                    log.error("broker unavailable while reading", error=str(exc))
                    await asyncio.sleep(settings.worker.retry_delay_s)
                    continue

                for message_id, fields in batch:
                    try:
                        await handle_message(
                            message_id,
                            fields,
                            consumer=consumer,
                            http_client=http_client,
                            semaphore=semaphore,
                        )
                    except RedisError as exc:
                        log.error("broker unavailable while handling", error=str(exc))
                        await asyncio.sleep(settings.worker.retry_delay_s)
                        break
                    if stop_event.is_set():
                        log.info("shutdown requested, finishing current batch")
    finally:
        log.info("worker stopping")
        await redis_helper.close()
        await db_helper.dispose()
        log.info("worker stopped")


if __name__ == "__main__":
    asyncio.run(run_worker())
