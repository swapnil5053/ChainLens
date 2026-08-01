"""Retry with backoff for the generation provider.

Only transient failures are retried. A 400 is a bug in the request and retrying it wastes
the user's time three times over; a 429 or a 5xx is worth another attempt. The total time
is bounded so a retry policy can never exceed the request timeout it sits inside, which is
the failure mode that turns a slow upstream into a hung request.
"""

from __future__ import annotations

from collections.abc import Callable, Iterator
from typing import TypeVar

import httpx
from tenacity import (
    RetryCallState,
    retry,
    retry_if_exception,
    stop_after_attempt,
    stop_after_delay,
    wait_exponential_jitter,
)

from ..logging import get_logger

logger = get_logger(__name__)
T = TypeVar("T")

RETRYABLE_STATUS = frozenset({408, 425, 429, 500, 502, 503, 504})


def is_transient(exception: BaseException) -> bool:
    if isinstance(exception, httpx.TimeoutException | httpx.ConnectError):
        return True
    if isinstance(exception, httpx.HTTPStatusError):
        return exception.response.status_code in RETRYABLE_STATUS
    return False


def _log(state: RetryCallState) -> None:
    logger.warning(
        "generation_retry",
        attempt=state.attempt_number,
        seconds=round(state.idle_for, 2),
        error=str(state.outcome.exception()) if state.outcome else None,
    )


def with_retry(
    function: Callable[[], Iterator[T]], *, attempts: int = 3, max_seconds: float = 20.0
) -> Iterator[T]:
    """Retry the establishment of a stream, not the stream itself.

    Once tokens have been yielded to the caller a retry would duplicate output, so the
    retry wraps the call that opens the stream and stops the moment the first token is
    handed on.
    """

    @retry(
        retry=retry_if_exception(is_transient),
        stop=stop_after_attempt(attempts) | stop_after_delay(max_seconds),
        wait=wait_exponential_jitter(initial=0.5, max=4.0),
        before_sleep=_log,
        reraise=True,
    )
    def open_stream() -> Iterator[T]:
        iterator = function()
        first = next(iterator, None)
        return iter(()) if first is None else _prepend(first, iterator)

    return open_stream()


def _prepend(first: T, rest: Iterator[T]) -> Iterator[T]:
    yield first
    yield from rest
