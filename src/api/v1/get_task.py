import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from database.db_helper import db_helper
from schemas.task_result import TaskResultResponse
from services import task_service
from services.exceptions import TaskNotFoundError

router = APIRouter()


@router.get(
    "/task/{task_id}",
    response_model=TaskResultResponse,
    summary="Получить статус и результаты задачи",
)
async def get_task(
    task_id: uuid.UUID,
    session: Annotated[AsyncSession, Depends(db_helper.session_getter)],
) -> TaskResultResponse:
    """Возвращает статус задачи и результаты проверок, готовые на текущий момент."""
    try:
        return await task_service.get_task_state(session=session, task_id=task_id)
    except TaskNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
