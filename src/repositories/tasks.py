import uuid

from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from database.models.tasks import Tasks
from schemas.enums import TaskStatus


async def create(
    session: AsyncSession,
    *,
    task_id: uuid.UUID,
    total_urls: int,
) -> Tasks:
    task = Tasks(
        id=task_id,
        status=TaskStatus.QUEUED,
        total_urls=total_urls,
    )
    session.add(task)
    await session.flush()
    return task


async def get(session: AsyncSession, task_id: uuid.UUID) -> Tasks | None:
    return await session.get(Tasks, task_id)


async def set_status(
    session: AsyncSession,
    *,
    task_id: uuid.UUID,
    status: TaskStatus,
) -> None:
    await session.execute(
        update(Tasks).where(Tasks.id == task_id).values(status=status)
    )
