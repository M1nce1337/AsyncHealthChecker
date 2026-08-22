from sqlalchemy import Enum as SAEnum, Integer, TIMESTAMP, func
from sqlalchemy.orm import Mapped, mapped_column
from database.models.base import Base
from schemas.enums import TaskStatus
import uuid
import datetime

class Tasks(Base):
    __tablename__ = "tasks"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True)
    status: Mapped[TaskStatus] = mapped_column(
        SAEnum(
            TaskStatus,
            name="task_status",
            values_callable=lambda enum: [member.value for member in enum],
        ),
        nullable=False,
        index=True,
        default=TaskStatus.QUEUED,
        server_default=TaskStatus.QUEUED.value,
    )
    total_urls: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime.datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime.datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )
