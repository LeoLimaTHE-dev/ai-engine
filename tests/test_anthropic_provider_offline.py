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

from ai_engine.models import DocumentContent, DocumentImage
from ai_engine.providers import anthropic_provider
from ai_engine.providers.errors import (
    ProviderConnectionError,
    ProviderError,
    ProviderRateLimitError,
    ProviderRequestError,
    ProviderTimeoutError,
)
from ai_engine.structured_schema import get_structured_result_json_schema
from ai_engine.usage import UsageRecord


def successful_message(*, stop_reason="end_turn"):
    return SimpleNamespace(
        content=[
            SimpleNamespace(type="text", text='{"message":"Done","outputs":[]}')
        ],
        usage=SimpleNamespace(input_tokens=10, output_tokens=4),
        stop_reason=stop_reason,
    )


def arrange_payload_capture(monkeypatch, message=None):
    calls = []
    client_options = []
    message = message or successful_message()
    client = SimpleNamespace(
        messages=SimpleNamespace(
            create=lambda **kwargs: calls.append(kwargs) or message,
        )
    )

    def make_client(**kwargs):
        client_options.append(kwargs)
        return client

    monkeypatch.setattr(anthropic_provider, "Anthropic", make_client)
    return calls, client_options


def document_with_image():
    return DocumentContent(
        source_path=Path("document.txt"),
        text="Document content",
        images=[
            DocumentImage(
                name="image.png",
                data=b"image-data",
                media_type="image/png",
            )
        ],
    )


def test_native_structured_text_adds_canonical_output_config_and_returns_str(
    monkeypatch,
):
    calls, _ = arrange_payload_capture(monkeypatch)
    logs = []
    canonical_before = get_structured_result_json_schema()
    monkeypatch.setattr(anthropic_provider, "log_usage", logs.append)
    monkeypatch.setenv("ANTHROPIC_MODEL", "anthropic-test")

    result = anthropic_provider.ask_anthropic("Hello", native_structured=True)

    assert result == '{"message":"Done","outputs":[]}'
    assert isinstance(result, str)
    assert calls[0]["output_config"] == {
        "format": {
            "type": "json_schema",
            "schema": canonical_before,
        }
    }
    assert get_structured_result_json_schema() == canonical_before
    assert logs == [
        UsageRecord(
            provider="anthropic",
            model="anthropic-test",
            input_tokens=10,
            output_tokens=4,
            total_tokens=14,
        )
    ]


def test_default_text_payload_does_not_include_output_config(monkeypatch):
    calls, _ = arrange_payload_capture(monkeypatch)
    monkeypatch.setattr(anthropic_provider, "log_usage", lambda record: None)

    anthropic_provider.ask_anthropic("Hello")

    assert "output_config" not in calls[0]


def test_native_structured_document_preserves_multimodal_payload(monkeypatch):
    document = document_with_image()
    monkeypatch.setattr(anthropic_provider, "log_usage", lambda record: None)
    monkeypatch.setattr(anthropic_provider, "normalize_image", lambda image: image)

    default_calls, _ = arrange_payload_capture(monkeypatch)
    anthropic_provider.ask_anthropic_document(document, "Analyze")
    default_messages = default_calls[0]["messages"]

    native_message = successful_message()
    native_message.content.append(SimpleNamespace(type="text", text="second"))
    native_calls, _ = arrange_payload_capture(monkeypatch, native_message)
    result = anthropic_provider.ask_anthropic_document(
        document,
        "Analyze",
        native_structured=True,
    )

    assert native_calls[0]["messages"] == default_messages
    assert native_calls[0]["output_config"]["format"]["schema"] == (
        get_structured_result_json_schema()
    )
    assert result == '{"message":"Done","outputs":[]}\nsecond'


def test_native_structured_preserves_timeout_and_retry_configuration(monkeypatch):
    calls, client_options = arrange_payload_capture(monkeypatch)
    retry_options = []

    def fake_retry(operation, **kwargs):
        retry_options.append(kwargs)
        return operation()

    monkeypatch.setattr(anthropic_provider, "retry_provider_call", fake_retry)
    monkeypatch.setattr(anthropic_provider, "log_usage", lambda record: None)
    monkeypatch.setenv("AI_PROVIDER_TIMEOUT_SECONDS", "2.5")
    monkeypatch.setenv("AI_PROVIDER_MAX_RETRIES", "3")
    monkeypatch.setenv("AI_PROVIDER_RETRY_BASE_DELAY_SECONDS", "0.25")
    monkeypatch.setenv("AI_PROVIDER_RETRY_MAX_DELAY_SECONDS", "4")

    anthropic_provider.ask_anthropic("Hello", native_structured=True)

    assert len(calls) == 1
    assert client_options == [{"timeout": 2.5, "max_retries": 0}]
    assert retry_options == [
        {
            "max_retries": 3,
            "base_delay_seconds": 0.25,
            "max_delay_seconds": 4.0,
        }
    ]


@pytest.mark.parametrize(
    "stop_reason",
    [
        "refusal",
        "max_tokens",
        "model_context_window_exceeded",
        "pause_turn",
        "tool_use",
        "stop_sequence",
    ],
)
def test_native_structured_rejects_incompatible_stop_reasons(
    stop_reason,
    monkeypatch,
):
    arrange_payload_capture(monkeypatch, successful_message(stop_reason=stop_reason))
    logs = []
    monkeypatch.setattr(anthropic_provider, "log_usage", logs.append)

    with pytest.raises(ProviderRequestError, match=stop_reason) as captured:
        anthropic_provider.ask_anthropic("Hello", native_structured=True)

    assert captured.value.error_code == f"stop_reason_{stop_reason}"
    assert captured.value.retryable is False
    assert len(logs) == 1


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
    monkeypatch.setattr(anthropic_provider, "Anthropic", lambda **kwargs: client)
    monkeypatch.setattr(anthropic_provider, "log_usage", usage_logs.append)
    monkeypatch.setenv("AI_PROVIDER_MAX_RETRIES", "0")

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
    monkeypatch.setattr(anthropic_provider, "Anthropic", lambda **kwargs: client)
    monkeypatch.setenv("AI_PROVIDER_MAX_RETRIES", "0")

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
    monkeypatch.setattr(anthropic_provider, "Anthropic", lambda **kwargs: client)

    def fail_to_log(record):
        raise RuntimeError("CSV unavailable")

    monkeypatch.setattr(anthropic_provider, "log_usage", fail_to_log)

    with pytest.raises(RuntimeError, match="CSV unavailable") as captured:
        anthropic_provider.ask_anthropic("Hello")

    assert not isinstance(captured.value, ProviderError)


def test_native_structured_sdk_errors_keep_existing_normalization(monkeypatch):
    sdk_error = make_status_error(BadRequestError, 400)

    def raise_error(**kwargs):
        assert kwargs["output_config"]["format"]["type"] == "json_schema"
        raise sdk_error

    client = SimpleNamespace(messages=SimpleNamespace(create=raise_error))
    monkeypatch.setattr(anthropic_provider, "Anthropic", lambda **kwargs: client)
    monkeypatch.setenv("AI_PROVIDER_MAX_RETRIES", "0")

    with pytest.raises(ProviderRequestError) as captured:
        anthropic_provider.ask_anthropic("Hello", native_structured=True)

    assert captured.value.__cause__ is sdk_error
