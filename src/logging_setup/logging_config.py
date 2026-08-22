import logging
import sys

import structlog

from config import settings

shared_processors = [
    structlog.contextvars.merge_contextvars,
    structlog.stdlib.add_log_level,
    structlog.processors.TimeStamper(fmt="iso", utc=True),
    structlog.processors.StackInfoRenderer(),
    structlog.processors.format_exc_info,
]


def format_record(logger, method_name, event_dict):
    record = {
        "timestamp": event_dict.pop("timestamp", None),
        "level": event_dict.pop("level", None),
    }
    task_id = event_dict.pop("task_id", None)
    if task_id is not None:
        record["task_id"] = str(task_id)
    record["message"] = event_dict.pop("event", None)

    exception = event_dict.pop("exception", None)
    if exception is not None:
        record["exception"] = exception

    event_dict.pop("logger", None)
    if event_dict:
        record["extra"] = event_dict
    return record


def setup_logging() -> None:
    structlog.configure(
        processors=[
            *shared_processors,
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )

    if settings.log.json_format:
        render = [format_record, structlog.processors.JSONRenderer(ensure_ascii=False)]
    else:
        render = [structlog.dev.ConsoleRenderer()]

    formatter = structlog.stdlib.ProcessorFormatter(
        foreign_pre_chain=shared_processors,
        processors=[
            structlog.stdlib.ProcessorFormatter.remove_processors_meta,
            *render,
        ],
    )

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)

    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(settings.log.level)

    for name in ("uvicorn", "uvicorn.error", "uvicorn.access"):
        logger = logging.getLogger(name)
        logger.handlers = []
        logger.propagate = True
