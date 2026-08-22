import pytest

from ai_engine.providers.errors import (
    ProviderConnectionError,
    ProviderError,
    ProviderRateLimitError,
    ProviderRequestError,
    ProviderTimeoutError,
    parse_retry_after_seconds,
)


def test_provider_error_preserves_message_and_all_metadata():
    details = {"reason": "quota_exhausted"}
    error = ProviderError(
        provider="gemini",
        message="Provider quota exceeded.",
        status_code=429,
        error_code="RESOURCE_EXHAUSTED",
        retry_after_seconds=34.58,
        retryable=False,
        details=details,
    )

    assert str(error) == "Provider quota exceeded."
    assert error.args == ("Provider quota exceeded.",)
    assert error.provider == "gemini"
    assert error.message == "Provider quota exceeded."
    assert error.status_code == 429
    assert error.error_code == "RESOURCE_EXHAUSTED"
    assert error.retry_after_seconds == 34.58
    assert error.retryable is False
    assert error.details is details


def test_provider_error_supports_absent_optional_metadata():
    error = ProviderError(
        provider="openai",
        message="Unexpected provider failure.",
        retryable=False,
    )

    assert error.status_code is None
    assert error.error_code is None
    assert error.retry_after_seconds is None
    assert error.details is None


@pytest.mark.parametrize(
    ("error_type", "retryable"),
    [
        (ProviderRateLimitError, True),
        (ProviderRateLimitError, False),
        (ProviderTimeoutError, True),
        (ProviderConnectionError, True),
        (ProviderRequestError, False),
        (ProviderRequestError, True),
    ],
)
def test_provider_error_subclasses_preserve_explicit_retryable_value(
    error_type,
    retryable,
):
    error = error_type(
        provider="provider",
        message="Failure",
        retryable=retryable,
    )

    assert isinstance(error, ProviderError)
    assert type(error) is error_type
    assert error.retryable is retryable


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("34.58", 34.58),
        (2, 2.0),
        (0, 0.0),
    ],
)
def test_parse_retry_after_accepts_numeric_seconds(value, expected):
    assert parse_retry_after_seconds(retry_after=value) == expected


def test_parse_retry_after_converts_milliseconds_and_gives_them_priority():
    assert (
        parse_retry_after_seconds(
            retry_after="20",
            retry_after_ms="1500",
        )
        == 1.5
    )


def test_parse_retry_after_falls_back_to_seconds_when_milliseconds_are_invalid():
    assert (
        parse_retry_after_seconds(
            retry_after="3.5",
            retry_after_ms="invalid",
        )
        == 3.5
    )


@pytest.mark.parametrize(
    ("retry_after", "retry_after_ms"),
    [
        (None, None),
        ("invalid", None),
        (-1, None),
        (None, -1),
        (float("inf"), None),
        (True, None),
    ],
)
def test_parse_retry_after_rejects_absent_or_invalid_values(
    retry_after,
    retry_after_ms,
):
    assert (
        parse_retry_after_seconds(
            retry_after=retry_after,
            retry_after_ms=retry_after_ms,
        )
        is None
    )
