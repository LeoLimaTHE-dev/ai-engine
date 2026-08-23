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

from ai_engine.models import DocumentContent, DocumentImage
from ai_engine.providers import gemini_provider
from ai_engine.providers.errors import (
    ProviderConnectionError,
    ProviderError,
    ProviderRateLimitError,
    ProviderRequestError,
    ProviderTimeoutError,
)
from ai_engine.structured_schema import get_structured_result_json_schema
from ai_engine.usage import UsageRecord


def successful_interaction(*, status="completed", errors=None):
    return SimpleNamespace(
        output_text='{"message":"Done","outputs":[]}',
        usage=SimpleNamespace(
            total_input_tokens=10,
            total_output_tokens=4,
            total_thought_tokens=2,
            total_cached_tokens=3,
            total_tokens=19,
        ),
        status=status,
        errors=errors,
    )


def arrange_payload_capture(monkeypatch, interaction=None):
    calls = []
    client_options = []
    interaction = interaction or successful_interaction()
    client = SimpleNamespace(
        interactions=SimpleNamespace(
            create=lambda **kwargs: calls.append(kwargs) or interaction,
        )
    )

    def make_client(**kwargs):
        client_options.append(kwargs)
        return client

    monkeypatch.setattr(gemini_provider.genai, "Client", make_client)
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


def test_native_structured_text_adds_canonical_json_response_format(monkeypatch):
    calls, _ = arrange_payload_capture(monkeypatch)
    logs = []
    canonical_before = get_structured_result_json_schema()
    monkeypatch.setattr(gemini_provider, "log_usage", logs.append)
    monkeypatch.setenv("GEMINI_MODEL", "gemini-test")

    result = gemini_provider.ask_gemini("Hello", native_structured=True)

    assert result == '{"message":"Done","outputs":[]}'
    assert isinstance(result, str)
    assert calls[0]["response_format"] == {
        "type": "text",
        "mime_type": "application/json",
        "schema": canonical_before,
    }
    assert get_structured_result_json_schema() == canonical_before
    assert logs == [
        UsageRecord(
            provider="gemini",
            model="gemini-test",
            input_tokens=10,
            output_tokens=4,
            thought_tokens=2,
            cached_tokens=3,
            total_tokens=19,
        )
    ]


def test_default_text_payload_does_not_include_response_format(monkeypatch):
    calls, _ = arrange_payload_capture(monkeypatch)
    monkeypatch.setattr(gemini_provider, "log_usage", lambda record: None)

    gemini_provider.ask_gemini("Hello")

    assert "response_format" not in calls[0]


def test_native_structured_document_preserves_multimodal_input(monkeypatch):
    document = document_with_image()
    monkeypatch.setattr(gemini_provider, "log_usage", lambda record: None)
    monkeypatch.setattr(gemini_provider, "normalize_image", lambda image: image)

    default_calls, _ = arrange_payload_capture(monkeypatch)
    gemini_provider.ask_gemini_document(document, "Analyze")
    default_input = default_calls[0]["input"]

    native_calls, _ = arrange_payload_capture(monkeypatch)
    result = gemini_provider.ask_gemini_document(
        document,
        "Analyze",
        native_structured=True,
    )

    assert native_calls[0]["input"] == default_input
    assert native_calls[0]["response_format"]["schema"] == (
        get_structured_result_json_schema()
    )
    assert result == '{"message":"Done","outputs":[]}'


def test_native_structured_preserves_timeout_and_sdk_retry_configuration(monkeypatch):
    calls, client_options = arrange_payload_capture(monkeypatch)
    monkeypatch.setattr(gemini_provider, "log_usage", lambda record: None)
    monkeypatch.setenv("AI_PROVIDER_TIMEOUT_SECONDS", "2.5")

    gemini_provider.ask_gemini("Hello", native_structured=True)

    assert len(calls) == 1
    assert len(client_options) == 1
    http_options = client_options[0]["http_options"]
    assert http_options.timeout == 2500
    assert http_options.retry_options is None


@pytest.mark.parametrize(
    "status",
    [
        "in_progress",
        "requires_action",
        "failed",
        "cancelled",
        "incomplete",
        "budget_exceeded",
        "queued",
        "future_status",
    ],
)
def test_native_structured_rejects_non_completed_statuses(status, monkeypatch):
    errors = [SimpleNamespace(code="failure", message="Not completed")]
    arrange_payload_capture(
        monkeypatch,
        successful_interaction(status=status, errors=errors),
    )
    logs = []
    monkeypatch.setattr(gemini_provider, "log_usage", logs.append)

    with pytest.raises(ProviderRequestError, match=status) as captured:
        gemini_provider.ask_gemini("Hello", native_structured=True)

    assert captured.value.error_code == f"interaction_{status}"
    assert captured.value.retryable is False
    assert captured.value.details is errors
    assert len(logs) == 1


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
    monkeypatch.setattr(gemini_provider.genai, "Client", lambda **kwargs: client)
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
    monkeypatch.setattr(gemini_provider.genai, "Client", lambda **kwargs: client)

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
    monkeypatch.setattr(gemini_provider.genai, "Client", lambda **kwargs: client)

    def fail_to_log(record):
        raise RuntimeError("CSV unavailable")

    monkeypatch.setattr(gemini_provider, "log_usage", fail_to_log)

    with pytest.raises(RuntimeError, match="CSV unavailable") as captured:
        gemini_provider.ask_gemini("Hello")

    assert not isinstance(captured.value, ProviderError)


def test_native_structured_sdk_errors_keep_existing_normalization(monkeypatch):
    sdk_error = make_status_error(BadRequestError, 400)

    def raise_error(**kwargs):
        assert kwargs["response_format"]["mime_type"] == "application/json"
        raise sdk_error

    client = SimpleNamespace(interactions=SimpleNamespace(create=raise_error))
    monkeypatch.setattr(gemini_provider.genai, "Client", lambda **kwargs: client)

    with pytest.raises(ProviderRequestError) as captured:
        gemini_provider.ask_gemini("Hello", native_structured=True)

    assert captured.value.__cause__ is sdk_error
