import uuid


class TaskNotFoundError(Exception):
    """Задачи с таким идентификатором нет в базе."""

    def __init__(self, task_id: uuid.UUID):
        self.task_id = task_id
        super().__init__(f"Задача {task_id} не найдена")


class TaskPublishError(Exception):
    """Задачу не удалось опубликовать в очередь брокера."""

    def __init__(self, task_id: uuid.UUID):
        self.task_id = task_id
        super().__init__(f"Задача {task_id} не опубликована в очередь")
