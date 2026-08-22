from pathlib import Path
from types import SimpleNamespace

import httpx
import pytest
from anthropic import (
    APIConnectionError,
    APITimeoutError,
    AnthropicError,
    AuthenticationError,
    BadRequestError,
    InternalServerError,
    NotFoundError,
    OverloadedError,
    PermissionDeniedError,
    RateLimitError,
    RequestTooLargeError,
)

from ai_engine.models import DocumentContent
from ai_engine.providers import anthropic_provider
from ai_engine.providers.errors import (
    ProviderConnectionError,
    ProviderError,
    ProviderRateLimitError,
    ProviderRequestError,
    ProviderTimeoutError,
)


def make_status_error(
    error_type,
    status_code,
    *,
    headers=None,
    message="Anthropic failure",
    body=None,
):
    request = httpx.Request("POST", "https://anthropic.invalid/v1/messages")
    response = httpx.Response(
        status_code,
        request=request,
        headers=headers,
    )

    return error_type(
        message,
        response=response,
        body=body,
    )


def call_text_with_error(monkeypatch, sdk_error):
    def raise_error(**kwargs):
        raise sdk_error

    client = SimpleNamespace(
        messages=SimpleNamespace(create=raise_error),
    )
    usage_logs = []
    monkeypatch.setattr(anthropic_provider, "Anthropic", lambda: client)
    monkeypatch.setattr(anthropic_provider, "log_usage", usage_logs.append)

    with pytest.raises(ProviderError) as captured:
        anthropic_provider.ask_anthropic("Hello")

    assert usage_logs == []

    return captured.value


@pytest.mark.parametrize(
    ("sdk_error", "expected_type", "retryable", "status_code"),
    [
        (
            make_status_error(
                RateLimitError,
                429,
                headers={"retry-after": "2.5"},
            ),
            ProviderRateLimitError,
            True,
            429,
        ),
        (
            APITimeoutError(
                httpx.Request("POST", "https://anthropic.invalid/v1/messages")
            ),
            ProviderTimeoutError,
            True,
            None,
        ),
        (
            APIConnectionError(
                request=httpx.Request(
                    "POST",
                    "https://anthropic.invalid/v1/messages",
                )
            ),
            ProviderConnectionError,
            True,
            None,
        ),
        (
            make_status_error(BadRequestError, 400),
            ProviderRequestError,
            False,
            400,
        ),
        (
            make_status_error(AuthenticationError, 401),
            ProviderRequestError,
            False,
            401,
        ),
        (
            make_status_error(PermissionDeniedError, 403),
            ProviderRequestError,
            False,
            403,
        ),
        (
            make_status_error(NotFoundError, 404),
            ProviderRequestError,
            False,
            404,
        ),
        (
            make_status_error(RequestTooLargeError, 413),
            ProviderRequestError,
            False,
            413,
        ),
        (
            make_status_error(InternalServerError, 500),
            ProviderError,
            True,
            500,
        ),
        (
            make_status_error(OverloadedError, 529),
            ProviderError,
            True,
            529,
        ),
        (
            AnthropicError("Unexpected Anthropic failure"),
            ProviderError,
            False,
            None,
        ),
    ],
)
def test_ask_anthropic_normalizes_known_sdk_errors(
    sdk_error,
    expected_type,
    retryable,
    status_code,
    monkeypatch,
):
    error = call_text_with_error(monkeypatch, sdk_error)

    assert type(error) is expected_type
    assert error.provider == "anthropic"
    assert error.retryable is retryable
    assert error.status_code == status_code
    assert error.__cause__ is sdk_error


def test_rate_limit_preserves_type_details_and_retry_after_ms(monkeypatch):
    details = {
        "error": {
            "type": "rate_limit_error",
            "message": "Structured rate limit",
        }
    }
    sdk_error = make_status_error(
        RateLimitError,
        429,
        headers={
            "retry-after": "20",
            "retry-after-ms": "1500",
        },
        body=details,
    )

    error = call_text_with_error(monkeypatch, sdk_error)

    assert isinstance(error, ProviderRateLimitError)
    assert error.error_code == "rate_limit_error"
    assert error.details is details
    assert error.retry_after_seconds == 1.5
    assert error.retryable is True


def test_rate_limit_without_structured_retry_after_does_not_parse_message(
    monkeypatch,
):
    sdk_error = make_status_error(
        RateLimitError,
        429,
        message="Please retry in 34.58s",
    )

    error = call_text_with_error(monkeypatch, sdk_error)

    assert isinstance(error, ProviderRateLimitError)
    assert str(error) == "Please retry in 34.58s"
    assert error.retry_after_seconds is None
    assert error.retryable is False


def test_document_call_uses_the_same_anthropic_error_normalization(monkeypatch):
    sdk_error = APITimeoutError(
        httpx.Request("POST", "https://anthropic.invalid/v1/messages")
    )

    def raise_error(**kwargs):
        raise sdk_error

    client = SimpleNamespace(
        messages=SimpleNamespace(create=raise_error),
    )
    monkeypatch.setattr(anthropic_provider, "Anthropic", lambda: client)

    with pytest.raises(ProviderTimeoutError) as captured:
        anthropic_provider.ask_anthropic_document(
            DocumentContent(source_path=Path("document.txt"), text="Content"),
            "Analyze",
        )

    assert captured.value.__cause__ is sdk_error


def test_log_usage_error_is_not_normalized_as_provider_error(monkeypatch):
    response = SimpleNamespace(
        content=[SimpleNamespace(type="text", text="Anthropic response")],
        usage=SimpleNamespace(input_tokens=1, output_tokens=1),
    )
    client = SimpleNamespace(
        messages=SimpleNamespace(create=lambda **kwargs: response),
    )
    monkeypatch.setattr(anthropic_provider, "Anthropic", lambda: client)

    def fail_to_log(record):
        raise RuntimeError("CSV unavailable")

    monkeypatch.setattr(anthropic_provider, "log_usage", fail_to_log)

    with pytest.raises(RuntimeError, match="CSV unavailable") as captured:
        anthropic_provider.ask_anthropic("Hello")

    assert not isinstance(captured.value, ProviderError)
