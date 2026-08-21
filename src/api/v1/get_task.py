import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from database.db_helper import db_helper
from database.models.check_results import CheckResults
from schemas.check_result import CheckResultRead
from schemas.enums import TaskStatus
from schemas.task_result import TaskResultResponse

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
    """Возвращает результаты проверок, сохранённые воркером для данной задачи."""
    stmt = (
        select(CheckResults)
        .where(CheckResults.task_id == task_id)
        .order_by(CheckResults.id)
    )
    rows = (await session.scalars(stmt)).all()

    if not rows:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Задача {task_id} не найдена",
        )

    results = [CheckResultRead.model_validate(row) for row in rows]
    # TODO(этап 3): total_urls и статус задачи брать из хранилища метаданных задачи
    # (задача попадает туда при постановке в очередь), сейчас они выводятся из
    # уже сохранённых результатов проверок.
    return TaskResultResponse(
        task_id=task_id,
        status=TaskStatus.COMPLETED,
        total_urls=len(results),
        processed_urls=len(results),
        results=results,
    )
