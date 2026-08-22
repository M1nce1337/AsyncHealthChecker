import datetime
import uuid

from pydantic import BaseModel, Field, HttpUrl

from schemas.task_create import MAX_URLS_PER_TASK


class TaskMessage(BaseModel):
    """Контракт сообщения, которым API и воркер обмениваются через очередь."""

    task_id: uuid.UUID
    urls: list[HttpUrl] = Field(min_length=1, max_length=MAX_URLS_PER_TASK)
    created_at: datetime.datetime
    attempt: int = Field(default=0, ge=0)
