import datetime
import uuid

from pydantic import BaseModel, Field

from schemas.enums import TaskStatus


class TaskCreatedResponse(BaseModel):
    """Ответ на создание задачи: идентификатор для последующего опроса статуса."""

    task_id: uuid.UUID
    status: TaskStatus = TaskStatus.QUEUED
    urls_count: int = Field(ge=1, description="Количество принятых на проверку URL")
    created_at: datetime.datetime
