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
from ai_engine.structured_schema import get_structured_result_json_schema
from ai_engine.usage import UsageRecord


def successful_response(*, output_text="Expected response", usage=None, **values):
    return SimpleNamespace(output_text=output_text, usage=usage, **values)


def arrange_payload_capture(monkeypatch, response=None):
    calls = []
    client_options = []
    response = response or successful_response()
    client = SimpleNamespace(
        responses=SimpleNamespace(
            create=lambda **kwargs: calls.append(kwargs) or response,
        )
    )

    def make_client(**kwargs):
        client_options.append(kwargs)
        return client

    monkeypatch.setattr(openai_provider, "OpenAI", make_client)
    return calls, client_options


def make_document():
    return DocumentContent(
        source_path=Path("example.txt"),
        text="Document content",
    )


def test_native_structured_text_adds_canonical_strict_schema(monkeypatch):
    calls, _ = arrange_payload_capture(monkeypatch)
    canonical_before = get_structured_result_json_schema()

    result = openai_provider.ask_openai("Hello", native_structured=True)

    assert result == "Expected response"
    assert calls[0]["input"] == "Hello"
    assert calls[0]["text"] == {
        "format": {
            "type": "json_schema",
            "name": "structured_result",
            "schema": canonical_before,
            "strict": True,
        }
    }
    assert get_structured_result_json_schema() == canonical_before


def test_native_structured_document_preserves_multimodal_input(monkeypatch):
    default_calls, _ = arrange_payload_capture(monkeypatch)
    openai_provider.ask_openai_document(make_document(), "Analyze")
    default_input = default_calls[0]["input"]

    native_calls, _ = arrange_payload_capture(monkeypatch)
    result = openai_provider.ask_openai_document(
        make_document(),
        "Analyze",
        native_structured=True,
    )

    assert result == "Expected response"
    assert native_calls[0]["input"] == default_input
    assert native_calls[0]["text"]["format"]["schema"] == (
        get_structured_result_json_schema()
    )


@pytest.mark.parametrize("operation", ["text", "document"])
def test_native_structured_preserves_usage_timeout_and_native_retry_settings(
    operation,
    monkeypatch,
):
    usage = SimpleNamespace(input_tokens=10, output_tokens=4, total_tokens=14)
    calls, client_options = arrange_payload_capture(
        monkeypatch,
        successful_response(usage=usage),
    )
    logs = []
    monkeypatch.setattr(openai_provider, "log_usage", logs.append)
    monkeypatch.setenv("AI_PROVIDER_TIMEOUT_SECONDS", "2.5")
    monkeypatch.setenv("OPENAI_MODEL", "openai-test")

    if operation == "text":
        result = openai_provider.ask_openai("Hello", native_structured=True)
    else:
        result = openai_provider.ask_openai_document(
            make_document(),
            "Analyze",
            native_structured=True,
        )

    assert result == "Expected response"
    assert len(calls) == 1
    assert client_options == [{"timeout": 2.5, "max_retries": 0}]
    assert logs == [
        UsageRecord(
            provider="openai",
            model="openai-test",
            input_tokens=10,
            output_tokens=4,
            total_tokens=14,
        )
    ]


@pytest.mark.parametrize(
    ("response", "error_code", "message"),
    [
        (
            successful_response(status="failed", error={"code": "failure"}),
            "response_failed",
            "was failed",
        ),
        (
            successful_response(
                status="incomplete",
                incomplete_details={"reason": "max_output_tokens"},
            ),
            "response_incomplete",
            "was incomplete",
        ),
        (
            successful_response(
                status="completed",
                output=[
                    SimpleNamespace(
                        content=[
                            SimpleNamespace(type="refusal", refusal="Cannot comply")
                        ]
                    )
                ],
            ),
            "response_refusal",
            "Cannot comply",
        ),
    ],
    ids=["failed", "incomplete", "refusal"],
)
def test_native_structured_rejects_non_result_response_states(
    response,
    error_code,
    message,
    monkeypatch,
):
    arrange_payload_capture(monkeypatch, response)

    with pytest.raises(ProviderRequestError, match=message) as captured:
        openai_provider.ask_openai("Hello", native_structured=True)

    assert captured.value.error_code == error_code
    assert captured.value.retryable is False


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


def test_native_structured_sdk_errors_keep_existing_normalization(monkeypatch):
    sdk_error = make_status_error(BadRequestError, 400)

    def raise_error(**kwargs):
        assert kwargs["text"]["format"]["type"] == "json_schema"
        raise sdk_error

    client = SimpleNamespace(responses=SimpleNamespace(create=raise_error))
    monkeypatch.setattr(openai_provider, "OpenAI", lambda **kwargs: client)
    monkeypatch.setenv("AI_PROVIDER_MAX_RETRIES", "0")

    with pytest.raises(ProviderRequestError) as captured:
        openai_provider.ask_openai("Hello", native_structured=True)

    assert captured.value.__cause__ is sdk_error


def test_gemini_imports_structured_schema_for_its_opt_in_adapter():
    providers_dir = Path(openai_provider.__file__).parent

    source = providers_dir.joinpath("gemini_provider.py").read_text(encoding="utf-8")
    assert "structured_schema" in source
    assert "get_structured_result_json_schema" in source
