import datetime

from pydantic import BaseModel, ConfigDict


class CheckResultRead(BaseModel):
    """Результат проверки одного URL-адреса."""

    model_config = ConfigDict(from_attributes=True)

    url: str
    status_code: int | None = None
    response_time: float | None = None
    is_available: bool
    error_message: str | None = None
    checked_at: datetime.datetime
