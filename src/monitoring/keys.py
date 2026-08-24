from config import settings


def tasks_processed_key() -> str:
    return f"{settings.redis.metrics_prefix}:tasks_processed"


def tasks_failed_key() -> str:
    return f"{settings.redis.metrics_prefix}:tasks_failed"


def urls_checked_key(status: str) -> str:
    return f"{settings.redis.metrics_prefix}:urls_checked:{status}"


def heartbeat_key(consumer_name: str) -> str:
    return f"{settings.redis.metrics_prefix}:alive:{consumer_name}"


def heartbeat_pattern() -> str:
    return f"{settings.redis.metrics_prefix}:alive:*"
