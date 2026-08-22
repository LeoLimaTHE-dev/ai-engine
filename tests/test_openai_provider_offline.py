from pathlib import Path
from types import SimpleNamespace

import httpx2
import pytest
from openai import (
    APIConnectionError,
    APITimeoutError,
    AuthenticationError,
    BadRequestError,
    InternalServerError,
    NotFoundError,
    OpenAIError,
    PermissionDeniedError,
    RateLimitError,
)

from ai_engine.models import DocumentContent
from ai_engine.providers import openai_provider
from ai_engine.providers.errors import (
    ProviderConnectionError,
    ProviderError,
    ProviderRateLimitError,
    ProviderRequestError,
    ProviderTimeoutError,
)


def test_ask_openai_document_returns_output_text_without_usage(monkeypatch):
    response = SimpleNamespace(
        usage=None,
        output_text="Expected response",
    )
    create_calls = []

    def fake_create(**kwargs):
        create_calls.append(kwargs)
        return response

    fake_client = SimpleNamespace(
        responses=SimpleNamespace(create=fake_create),
    )

    monkeypatch.setattr(openai_provider, "OpenAI", lambda **kwargs: fake_client)

    def fail_if_usage_is_logged(*args, **kwargs):
        raise AssertionError("log_usage must not run when response.usage is None")

    monkeypatch.setattr(openai_provider, "log_usage", fail_if_usage_is_logged)

    document = DocumentContent(
        source_path=Path("example.txt"),
        text="Document content",
    )

    result = openai_provider.ask_openai_document(
        document=document,
        prompt="Analyze",
    )

    assert len(create_calls) == 1
    assert result == "Expected response"


def make_status_error(
    error_type,
    status_code,
    *,
    headers=None,
    message="OpenAI failure",
    body=None,
):
    request = httpx2.Request("POST", "https://openai.invalid/v1/responses")
    response = httpx2.Response(
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
        responses=SimpleNamespace(create=raise_error),
    )
    usage_logs = []
    monkeypatch.setattr(openai_provider, "OpenAI", lambda **kwargs: client)
    monkeypatch.setattr(openai_provider, "log_usage", usage_logs.append)
    monkeypatch.setenv("AI_PROVIDER_MAX_RETRIES", "0")

    with pytest.raises(ProviderError) as captured:
        openai_provider.ask_openai("Hello")

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
                httpx2.Request("POST", "https://openai.invalid/v1/responses")
            ),
            ProviderTimeoutError,
            True,
            None,
        ),
        (
            APIConnectionError(
                request=httpx2.Request(
                    "POST",
                    "https://openai.invalid/v1/responses",
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
            OpenAIError("Unexpected OpenAI failure"),
            ProviderError,
            False,
            None,
        ),
    ],
)
def test_ask_openai_normalizes_known_sdk_errors(
    sdk_error,
    expected_type,
    retryable,
    status_code,
    monkeypatch,
):
    error = call_text_with_error(monkeypatch, sdk_error)

    assert type(error) is expected_type
    assert error.provider == "openai"
    assert error.retryable is retryable
    assert error.status_code == status_code
    assert error.__cause__ is sdk_error


def test_rate_limit_preserves_code_details_and_retry_after_ms(monkeypatch):
    details = {
        "code": "rate_limit_exceeded",
        "message": "Structured rate limit",
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
    assert error.error_code == "rate_limit_exceeded"
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


def test_document_call_uses_the_same_openai_error_normalization(monkeypatch):
    sdk_error = APITimeoutError(
        httpx2.Request("POST", "https://openai.invalid/v1/responses")
    )

    def raise_error(**kwargs):
        raise sdk_error

    client = SimpleNamespace(
        responses=SimpleNamespace(create=raise_error),
    )
    monkeypatch.setattr(openai_provider, "OpenAI", lambda **kwargs: client)
    monkeypatch.setenv("AI_PROVIDER_MAX_RETRIES", "0")

    with pytest.raises(ProviderTimeoutError) as captured:
        openai_provider.ask_openai_document(
            DocumentContent(source_path=Path("document.txt"), text="Content"),
            "Analyze",
        )

    assert captured.value.__cause__ is sdk_error


def test_log_usage_error_is_not_normalized_as_provider_error(monkeypatch):
    response = SimpleNamespace(
        output_text="OpenAI response",
        usage=SimpleNamespace(input_tokens=1, output_tokens=1, total_tokens=2),
    )
    client = SimpleNamespace(
        responses=SimpleNamespace(create=lambda **kwargs: response),
    )
    monkeypatch.setattr(openai_provider, "OpenAI", lambda **kwargs: client)

    def fail_to_log(record):
        raise RuntimeError("CSV unavailable")

    monkeypatch.setattr(openai_provider, "log_usage", fail_to_log)

    with pytest.raises(RuntimeError, match="CSV unavailable") as captured:
        openai_provider.ask_openai("Hello")

    assert not isinstance(captured.value, ProviderError)
