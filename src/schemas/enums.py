from enum import Enum


class TaskStatus(str, Enum):
    """Состояние задачи на проверку URL-адресов."""

    QUEUED = "queued"
    PROCESSING = "processing"
    COMPLETED = "completed"
