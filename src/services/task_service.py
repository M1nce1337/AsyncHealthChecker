import uuid

import structlog
from redis.asyncio import Redis
from redis.exceptions import RedisError
from sqlalchemy.ext.asyncio import AsyncSession

from broker.producer import publish_task
from repositories import check_results as check_results_repo
from repositories import tasks as tasks_repo
from schemas.check_result import CheckResultRead
from schemas.enums import TaskStatus
from schemas.task_create import TaskCreateRequest
from schemas.task_created import TaskCreatedResponse
from schemas.task_message import TaskMessage
from schemas.task_result import TaskResultResponse
from services.exceptions import TaskNotFoundError, TaskPublishError

log = structlog.get_logger(__name__)


async def create_task(
    *,
    session: AsyncSession,
    redis: Redis,
    request: TaskCreateRequest,
) -> TaskCreatedResponse:
    task_id = uuid.uuid4()
    structlog.contextvars.bind_contextvars(task_id=str(task_id))

    try:
        task = await tasks_repo.create(
            session,
            task_id=task_id,
            total_urls=len(request.urls),
        )
        await session.commit()
        log.info("task created", urls_count=task.total_urls)

        message = TaskMessage(
            task_id=task.id,
            urls=request.urls,
            created_at=task.created_at,
        )
        try:
            await publish_task(redis, message)
        except RedisError as exc:
            log.error("task publishing failed", error=str(exc))
            await tasks_repo.set_status(
                session,
                task_id=task.id,
                status=TaskStatus.FAILED,
            )
            await session.commit()
            raise TaskPublishError(task.id) from exc

        return TaskCreatedResponse(
            task_id=task.id,
            status=task.status,
            urls_count=task.total_urls,
            created_at=task.created_at,
        )
    finally:
        structlog.contextvars.unbind_contextvars("task_id")


async def get_task_state(
    *,
    session: AsyncSession,
    task_id: uuid.UUID,
) -> TaskResultResponse:
    structlog.contextvars.bind_contextvars(task_id=str(task_id))
    try:
        task = await tasks_repo.get(session, task_id)
        if task is None:
            log.info("task not found")
            raise TaskNotFoundError(task_id)

        rows = await check_results_repo.get_by_task_id(session, task_id)
        log.debug(
            "task state requested",
            status=task.status.value,
            processed_urls=len(rows),
            total_urls=task.total_urls,
        )
        return TaskResultResponse(
            task_id=task.id,
            status=task.status,
            total_urls=task.total_urls,
            processed_urls=len(rows),
            results=[CheckResultRead.model_validate(row) for row in rows],
        )
    finally:
        structlog.contextvars.unbind_contextvars("task_id")
