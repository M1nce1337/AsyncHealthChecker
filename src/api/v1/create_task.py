from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from broker.redis_helper import redis_helper
from database.db_helper import db_helper
from schemas.task_create import TaskCreateRequest
from schemas.task_created import TaskCreatedResponse
from services import task_service
from services.exceptions import TaskPublishError

router = APIRouter()


@router.post(
    "/task",
    response_model=TaskCreatedResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Создать задачу на проверку URL-адресов",
)
async def create_task(
    payload: TaskCreateRequest,
    session: Annotated[AsyncSession, Depends(db_helper.session_getter)],
    redis: Annotated[Redis, Depends(redis_helper.client_getter)],
) -> TaskCreatedResponse:
    """Принимает список URL, регистрирует задачу и ставит её в очередь."""
    try:
        return await task_service.create_task(
            session=session,
            redis=redis,
            request=payload,
        )
    except TaskPublishError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Очередь задач недоступна, повторите запрос позже",
        ) from exc
