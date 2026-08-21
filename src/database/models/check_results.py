from sqlalchemy import Integer, String, Float, Boolean, Text, func
from sqlalchemy import TIMESTAMP
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.dialects.postgresql import UUID
from database.models.base import Base
import uuid
import datetime

class CheckResults(Base):
    __tablename__ = "check_results"

    task_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        index=True,
    )
    url: Mapped[str] = mapped_column(String(2048), nullable=False)
    status_code: Mapped[int] = mapped_column(Integer)
    response_time: Mapped[float] = mapped_column(Float)
    is_available: Mapped[bool] = mapped_column(Boolean)
    error_message: Mapped[str] = mapped_column(Text)
    checked_at: Mapped[datetime.datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
