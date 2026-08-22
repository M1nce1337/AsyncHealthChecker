import asyncio

import httpx
import structlog
from sqlalchemy.ext.asyncio import async_sessionmaker, AsyncSession

from database.models.check_results import CheckResults
from repositories import check_results as check_results_repo
from repositories import tasks as tasks_repo
from schemas.enums import TaskStatus
from schemas.task_message import TaskMessage
from services.url_checker import check_url

log = structlog.get_logger(__name__)


async def process_task(
    *,
    message: TaskMessage,
    session_factory: async_sessionmaker[AsyncSession],
    http_client: httpx.AsyncClient,
    semaphore: asyncio.Semaphore,
) -> None:
    """Проверяет все URL задачи и сохраняет результаты."""
    urls = [str(url) for url in message.urls]

    async with session_factory() as session:
        await tasks_repo.set_status(
            session,
            task_id=message.task_id,
            status=TaskStatus.PROCESSING,
        )
        await session.commit()

    log.info("task processing started", urls_count=len(urls), attempt=message.attempt)

    outcomes = await asyncio.gather(
        *(check_url(http_client, url, semaphore) for url in urls)
    )

    async with session_factory() as session:
        deleted = await check_results_repo.delete_by_task_id(session, message.task_id)
        await check_results_repo.bulk_create(
            session,
            (
                CheckResults(
                    task_id=message.task_id,
                    url=outcome.url,
                    status_code=outcome.status_code,
                    response_time=outcome.response_time,
                    is_available=outcome.is_available,
                    error_message=outcome.error_message,
                )
                for outcome in outcomes
            ),
        )
        await tasks_repo.set_status(
            session,
            task_id=message.task_id,
            status=TaskStatus.COMPLETED,
        )
        await session.commit()

    log.info(
        "task completed",
        urls_count=len(outcomes),
        available=sum(outcome.is_available for outcome in outcomes),
        unavailable=sum(not outcome.is_available for outcome in outcomes),
        replaced_rows=deleted,
    )


async def mark_failed(
    *,
    task_id,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with session_factory() as session:
        await tasks_repo.set_status(
            session,
            task_id=task_id,
            status=TaskStatus.FAILED,
        )
        await session.commit()
