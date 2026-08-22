import asyncio
import time
from dataclasses import dataclass

import httpx
import structlog

log = structlog.get_logger(__name__)


@dataclass(slots=True)
class UrlCheckOutcome:
    url: str
    status_code: int | None
    response_time: float | None
    is_available: bool
    error_message: str | None


async def check_url(
    client: httpx.AsyncClient,
    url: str,
    semaphore: asyncio.Semaphore,
) -> UrlCheckOutcome:
    """Одна HTTP-проверка. Никогда не бросает исключение наружу."""
    async with semaphore:
        started = time.perf_counter()
        try:
            async with client.stream("GET", url) as response:
                elapsed_ms = round((time.perf_counter() - started) * 1000, 2)
                outcome = UrlCheckOutcome(
                    url=url,
                    status_code=response.status_code,
                    response_time=elapsed_ms,
                    is_available=response.status_code < 400,
                    error_message=None,
                )

        except httpx.TimeoutException:
            outcome = _failure(url, "Connection timeout")
        except httpx.HTTPError as exc:
            outcome = _failure(url, f"{type(exc).__name__}: {exc}")
        except Exception as exc:
            outcome = _failure(url, f"Unexpected error: {type(exc).__name__}: {exc}")

    log.info(
        "url checked",
        url=outcome.url,
        status_code=outcome.status_code,
        response_time=outcome.response_time,
        is_available=outcome.is_available,
        error_message=outcome.error_message,
    )
    return outcome


def _failure(url: str, message: str) -> UrlCheckOutcome:
    return UrlCheckOutcome(
        url=url,
        status_code=None,
        response_time=None,
        is_available=False,
        error_message=message,
    )
