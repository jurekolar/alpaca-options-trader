"""Small retry helper for transient Alpaca API failures."""

from __future__ import annotations

from collections.abc import Callable
import logging
from time import sleep
from typing import TypeVar

LOGGER = logging.getLogger(__name__)

T = TypeVar("T")


def retry_call(
    operation: Callable[[], T],
    *,
    attempts: int = 3,
    base_delay_seconds: float = 0.5,
    retry_exceptions: tuple[type[BaseException], ...] = (Exception,),
    operation_name: str = "operation",
    should_retry: Callable[[BaseException], bool] | None = None,
) -> T:
    last_error: BaseException | None = None
    for attempt in range(1, attempts + 1):
        try:
            return operation()
        except retry_exceptions as exc:
            if should_retry is not None and not should_retry(exc):
                raise
            last_error = exc
            if attempt >= attempts:
                break
            delay = base_delay_seconds * (2 ** (attempt - 1))
            LOGGER.warning("%s failed on attempt %s/%s: %s", operation_name, attempt, attempts, exc)
            sleep(delay)
    assert last_error is not None
    raise last_error
