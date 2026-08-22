import uuid
from typing import Iterable, Sequence

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from database.models.check_results import CheckResults


async def get_by_task_id(
    session: AsyncSession,
    task_id: uuid.UUID,
) -> Sequence[CheckResults]:

    stmt = (
        select(CheckResults)
        .where(CheckResults.task_id == task_id)
        .order_by(CheckResults.id)
    )
    return (await session.scalars(stmt)).all()


async def delete_by_task_id(session: AsyncSession, task_id: uuid.UUID) -> int:

    result = await session.execute(
        delete(CheckResults).where(CheckResults.task_id == task_id)
    )
    return result.rowcount


async def bulk_create(
    session: AsyncSession,
    rows: Iterable[CheckResults],
) -> None:

    session.add_all(list(rows))
    await session.flush()
