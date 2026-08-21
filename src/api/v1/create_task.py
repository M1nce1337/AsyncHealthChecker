import datetime
import uuid

from fastapi import APIRouter, status

from schemas.enums import TaskStatus
from schemas.task_create import TaskCreateRequest
from schemas.task_created import TaskCreatedResponse

router = APIRouter()


@router.post(
    "/task",
    response_model=TaskCreatedResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Создать задачу на проверку URL-адресов",
)
async def create_task(payload: TaskCreateRequest) -> TaskCreatedResponse:
    """Принимает список URL, регистрирует задачу и возвращает её идентификатор."""
    task_id = uuid.uuid4()
    # TODO(этап 3): опубликовать задачу в очередь брокера (Redis Pub/Sub).
    return TaskCreatedResponse(
        task_id=task_id,
        status=TaskStatus.QUEUED,
        urls_count=len(payload.urls),
        created_at=datetime.datetime.now(datetime.timezone.utc),
    )
