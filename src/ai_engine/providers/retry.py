import math
import time
from collections.abc import Callable
from numbers import Real
from typing import TypeVar

from .errors import ProviderError


ResultT = TypeVar("ResultT")


def _validate_parameters(
    *,
    max_retries: int,
    base_delay_seconds: float,
    max_delay_seconds: float,
) -> None:
    if isinstance(max_retries, bool) or not isinstance(max_retries, int):
        raise TypeError("max_retries must be an integer")

    if max_retries < 0:
        raise ValueError("max_retries must be greater than or equal to zero")

    for name, value in (
        ("base_delay_seconds", base_delay_seconds),
        ("max_delay_seconds", max_delay_seconds),
    ):
        if isinstance(value, bool) or not isinstance(value, Real):
            raise TypeError(f"{name} must be a real number")

        if not math.isfinite(float(value)) or value < 0:
            raise ValueError(f"{name} must be a finite non-negative number")


def _retry_delay_seconds(
    exc: ProviderError,
    *,
    retry_index: int,
    base_delay_seconds: float,
    max_delay_seconds: float,
) -> float:
    retry_after = exc.retry_after_seconds

    if (
        isinstance(retry_after, Real)
        and not isinstance(retry_after, bool)
        and math.isfinite(float(retry_after))
        and retry_after > 0
    ):
        return min(float(retry_after), float(max_delay_seconds))

    delay = min(float(base_delay_seconds), float(max_delay_seconds))

    for _ in range(retry_index):
        delay = min(delay * 2, float(max_delay_seconds))

    return delay


def retry_provider_call(
    operation: Callable[[], ResultT],
    *,
    max_retries: int,
    base_delay_seconds: float,
    max_delay_seconds: float,
    sleep: Callable[[float], None] = time.sleep,
) -> ResultT:
    """Run a provider operation, retrying only explicitly retryable errors.

    ``max_retries`` is the number of calls allowed after the initial attempt.
    Delays use ``base_delay_seconds * 2**retry_index`` and are capped by
    ``max_delay_seconds``. A positive structured Retry-After takes precedence
    and is subject to the same cap.
    """
    _validate_parameters(
        max_retries=max_retries,
        base_delay_seconds=base_delay_seconds,
        max_delay_seconds=max_delay_seconds,
    )

    for retry_index in range(max_retries + 1):
        try:
            return operation()
        except ProviderError as exc:
            if not exc.retryable or retry_index == max_retries:
                raise

            delay = _retry_delay_seconds(
                exc,
                retry_index=retry_index,
                base_delay_seconds=base_delay_seconds,
                max_delay_seconds=max_delay_seconds,
            )

            if delay > 0:
                sleep(delay)

    raise AssertionError("retry loop completed without returning or raising")


__all__ = ["retry_provider_call"]
