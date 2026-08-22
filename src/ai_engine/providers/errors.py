import math


class ProviderError(Exception):
    def __init__(
        self,
        *,
        provider: str,
        message: str,
        status_code: int | None = None,
        error_code: str | None = None,
        retry_after_seconds: float | None = None,
        retryable: bool,
        details: object | None = None,
    ) -> None:
        super().__init__(message)
        self.provider = provider
        self.message = message
        self.status_code = status_code
        self.error_code = error_code
        self.retry_after_seconds = retry_after_seconds
        self.retryable = retryable
        self.details = details


class ProviderRateLimitError(ProviderError):
    pass


class ProviderTimeoutError(ProviderError):
    pass


class ProviderConnectionError(ProviderError):
    pass


class ProviderRequestError(ProviderError):
    pass


def _non_negative_number(value: object | None) -> float | None:
    if value is None or isinstance(value, bool):
        return None

    try:
        number = float(value)
    except (TypeError, ValueError):
        return None

    if not math.isfinite(number) or number < 0:
        return None

    return number


def parse_retry_after_seconds(
    *,
    retry_after: object | None = None,
    retry_after_ms: object | None = None,
) -> float | None:
    milliseconds = _non_negative_number(retry_after_ms)

    if milliseconds is not None:
        return milliseconds / 1000

    return _non_negative_number(retry_after)


__all__ = [
    "ProviderConnectionError",
    "ProviderError",
    "ProviderRateLimitError",
    "ProviderRequestError",
    "ProviderTimeoutError",
    "parse_retry_after_seconds",
]
