import uuid

from pydantic import BaseModel, Field

from schemas.check_result import CheckResultRead
from schemas.enums import TaskStatus


class TaskResultResponse(BaseModel):
    """Статус задачи и результаты проверок, доступные на текущий момент."""

    task_id: uuid.UUID
    status: TaskStatus
    total_urls: int = Field(ge=0, description="Всего URL в задаче")
    processed_urls: int = Field(ge=0, description="Сколько URL уже проверено")
    results: list[CheckResultRead] = Field(default_factory=list)
