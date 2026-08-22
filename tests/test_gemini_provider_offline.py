from pathlib import Path
from types import SimpleNamespace

import httpx
import pytest
from google.genai._gaos.lib.compat_errors import (
    APIConnectionError,
    APITimeoutError,
    AuthenticationError,
    BadRequestError,
    GeminiNextGenAPIClientError,
    InternalServerError,
    NotFoundError,
    PermissionDeniedError,
    RateLimitError,
)

from ai_engine.models import DocumentContent
from ai_engine.providers import gemini_provider
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
    message="Gemini failure",
    body=None,
):
    request = httpx.Request("POST", "https://gemini.invalid/v1/interactions")
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
        interactions=SimpleNamespace(create=raise_error),
    )
    usage_logs = []
    monkeypatch.setattr(gemini_provider.genai, "Client", lambda: client)
    monkeypatch.setattr(gemini_provider, "log_usage", usage_logs.append)

    with pytest.raises(ProviderError) as captured:
        gemini_provider.ask_gemini("Hello")

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
                httpx.Request("POST", "https://gemini.invalid/v1/interactions")
            ),
            ProviderTimeoutError,
            True,
            None,
        ),
        (
            APIConnectionError(
                request=httpx.Request(
                    "POST",
                    "https://gemini.invalid/v1/interactions",
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
            make_status_error(InternalServerError, 503),
            ProviderError,
            True,
            503,
        ),
        (
            GeminiNextGenAPIClientError("Unexpected Gemini failure"),
            ProviderError,
            False,
            None,
        ),
    ],
)
def test_ask_gemini_normalizes_interactions_sdk_errors(
    sdk_error,
    expected_type,
    retryable,
    status_code,
    monkeypatch,
):
    error = call_text_with_error(monkeypatch, sdk_error)

    assert type(error) is expected_type
    assert error.provider == "gemini"
    assert error.retryable is retryable
    assert error.status_code == status_code
    assert error.__cause__ is sdk_error


def test_rate_limit_preserves_structured_metadata_and_retry_after_ms(monkeypatch):
    details = {
        "error": {
            "code": 429,
            "status": "RESOURCE_EXHAUSTED",
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
    assert error.error_code == "RESOURCE_EXHAUSTED"
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


def test_document_call_uses_the_same_gemini_error_normalization(monkeypatch):
    sdk_error = APITimeoutError(
        httpx.Request("POST", "https://gemini.invalid/v1/interactions")
    )

    def raise_error(**kwargs):
        raise sdk_error

    client = SimpleNamespace(
        interactions=SimpleNamespace(create=raise_error),
    )
    monkeypatch.setattr(gemini_provider.genai, "Client", lambda: client)

    with pytest.raises(ProviderTimeoutError) as captured:
        gemini_provider.ask_gemini_document(
            DocumentContent(source_path=Path("document.txt"), text="Content"),
            "Analyze",
        )

    assert captured.value.__cause__ is sdk_error


def test_log_usage_error_is_not_normalized_as_provider_error(monkeypatch):
    interaction = SimpleNamespace(
        output_text="Gemini response",
        usage=SimpleNamespace(
            total_input_tokens=1,
            total_output_tokens=1,
            total_thought_tokens=0,
            total_cached_tokens=0,
            total_tokens=2,
        ),
    )
    client = SimpleNamespace(
        interactions=SimpleNamespace(create=lambda **kwargs: interaction),
    )
    monkeypatch.setattr(gemini_provider.genai, "Client", lambda: client)

    def fail_to_log(record):
        raise RuntimeError("CSV unavailable")

    monkeypatch.setattr(gemini_provider, "log_usage", fail_to_log)

    with pytest.raises(RuntimeError, match="CSV unavailable") as captured:
        gemini_provider.ask_gemini("Hello")

    assert not isinstance(captured.value, ProviderError)
