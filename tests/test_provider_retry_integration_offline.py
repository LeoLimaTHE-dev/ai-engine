from pathlib import Path
from types import SimpleNamespace

import httpx
import httpx2
import pytest
from anthropic import (
    APITimeoutError as AnthropicTimeoutError,
    APIConnectionError as AnthropicConnectionError,
    BadRequestError as AnthropicBadRequestError,
    InternalServerError as AnthropicServerError,
    RateLimitError as AnthropicRateLimitError,
)
from openai import (
    APIConnectionError as OpenAIConnectionError,
    APITimeoutError as OpenAITimeoutError,
    BadRequestError as OpenAIBadRequestError,
    InternalServerError as OpenAIServerError,
    RateLimitError as OpenAIRateLimitError,
)

from ai_engine.models import DocumentContent
from ai_engine.providers import anthropic_provider, openai_provider
from ai_engine.providers.errors import ProviderError, ProviderRateLimitError
from ai_engine.providers.retry import retry_provider_call as real_retry_provider_call


@pytest.fixture(autouse=True)
def clear_retry_environment(monkeypatch):
    for name in (
        "AI_PROVIDER_MAX_RETRIES",
        "AI_PROVIDER_RETRY_BASE_DELAY_SECONDS",
        "AI_PROVIDER_RETRY_MAX_DELAY_SECONDS",
    ):
        monkeypatch.delenv(name, raising=False)


def make_status_error(provider, kind, *, headers=None, message="Provider failure"):
    if provider == "openai":
        error_types = {
            "bad_request": OpenAIBadRequestError,
            "rate_limit": OpenAIRateLimitError,
            "server": OpenAIServerError,
        }
        status_codes = {"bad_request": 400, "rate_limit": 429, "server": 503}
        request = httpx2.Request("POST", "https://openai.invalid/v1/responses")
        response = httpx2.Response(
            status_codes[kind],
            request=request,
            headers=headers,
        )
    else:
        error_types = {
            "bad_request": AnthropicBadRequestError,
            "rate_limit": AnthropicRateLimitError,
            "server": AnthropicServerError,
        }
        status_codes = {"bad_request": 400, "rate_limit": 429, "server": 503}
        request = httpx.Request("POST", "https://anthropic.invalid/v1/messages")
        response = httpx.Response(
            status_codes[kind],
            request=request,
            headers=headers,
        )

    return error_types[kind](message, response=response, body={"kind": kind})


def make_transport_error(provider, kind, *, message="Provider failure"):
    if provider == "openai":
        request = httpx2.Request("POST", "https://openai.invalid/v1/responses")
        if kind == "timeout":
            return OpenAITimeoutError(request)
        return OpenAIConnectionError(request=request)

    request = httpx.Request("POST", "https://anthropic.invalid/v1/messages")
    if kind == "timeout":
        return AnthropicTimeoutError(request)
    return AnthropicConnectionError(message=message, request=request)


def success_response(provider):
    if provider == "openai":
        return SimpleNamespace(
            output_text="response",
            usage=SimpleNamespace(input_tokens=2, output_tokens=1, total_tokens=3),
        )

    return SimpleNamespace(
        content=[SimpleNamespace(type="text", text="response")],
        usage=SimpleNamespace(input_tokens=2, output_tokens=1),
    )


def arrange_provider_call(
    provider,
    outcomes,
    monkeypatch,
    *,
    operation="text",
    log_usage=None,
):
    module = openai_provider if provider == "openai" else anthropic_provider
    pending = list(outcomes)
    sdk_calls = []
    usage_logs = []
    sleeps = []
    client_options = []

    def create(**kwargs):
        sdk_calls.append(kwargs)
        outcome = pending.pop(0)
        if isinstance(outcome, BaseException):
            raise outcome
        return outcome

    if provider == "openai":
        client = SimpleNamespace(responses=SimpleNamespace(create=create))
        constructor_name = "OpenAI"
    else:
        client = SimpleNamespace(messages=SimpleNamespace(create=create))
        constructor_name = "Anthropic"

    def make_client(**kwargs):
        client_options.append(kwargs)
        return client

    def retry_without_real_sleep(operation, **kwargs):
        return real_retry_provider_call(operation, **kwargs, sleep=sleeps.append)

    monkeypatch.setattr(module, constructor_name, make_client)
    monkeypatch.setattr(module, "retry_provider_call", retry_without_real_sleep)
    monkeypatch.setattr(
        module,
        "log_usage",
        usage_logs.append if log_usage is None else log_usage,
    )

    def invoke():
        if operation == "text":
            return (
                module.ask_openai("Hello")
                if provider == "openai"
                else module.ask_anthropic("Hello")
            )

        document = DocumentContent(
            source_path=Path("document.txt"),
            text="Content",
        )
        return (
            module.ask_openai_document(document, "Analyze")
            if provider == "openai"
            else module.ask_anthropic_document(document, "Analyze")
        )

    return invoke, sdk_calls, usage_logs, sleeps, client_options


@pytest.mark.parametrize("provider", ["openai", "anthropic"])
def test_success_on_initial_attempt_calls_sdk_and_usage_once(provider, monkeypatch):
    invoke, sdk_calls, usage_logs, sleeps, client_options = arrange_provider_call(
        provider,
        [success_response(provider)],
        monkeypatch,
    )

    assert invoke() == "response"
    assert len(sdk_calls) == 1
    assert len(usage_logs) == 1
    assert sleeps == []
    assert client_options[0]["max_retries"] == 0


@pytest.mark.parametrize("provider", ["openai", "anthropic"])
@pytest.mark.parametrize("kind", ["timeout", "connection", "server", "rate_limit"])
def test_retryable_sdk_error_then_success_retries_only_remote_call(
    provider,
    kind,
    monkeypatch,
):
    if kind in {"timeout", "connection"}:
        error = make_transport_error(provider, kind)
        expected_sleep = [1.0]
    elif kind == "rate_limit":
        error = make_status_error(
            provider,
            kind,
            headers={"retry-after": "0.25"},
        )
        expected_sleep = [0.25]
    else:
        error = make_status_error(provider, kind)
        expected_sleep = [1.0]

    invoke, sdk_calls, usage_logs, sleeps, _ = arrange_provider_call(
        provider,
        [error, success_response(provider)],
        monkeypatch,
    )

    assert invoke() == "response"
    assert len(sdk_calls) == 2
    assert len(usage_logs) == 1
    assert sleeps == expected_sleep


@pytest.mark.parametrize("provider", ["openai", "anthropic"])
@pytest.mark.parametrize("kind", ["rate_limit", "bad_request"])
def test_non_retryable_normalized_error_is_not_repeated(provider, kind, monkeypatch):
    error = make_status_error(
        provider,
        kind,
        message="Please retry in 34.58s",
    )
    invoke, sdk_calls, usage_logs, sleeps, _ = arrange_provider_call(
        provider,
        [error],
        monkeypatch,
    )

    expected_type = ProviderRateLimitError if kind == "rate_limit" else ProviderError
    with pytest.raises(expected_type) as captured:
        invoke()

    assert captured.value.retryable is False
    assert captured.value.__cause__ is error
    assert len(sdk_calls) == 1
    assert usage_logs == []
    assert sleeps == []


@pytest.mark.parametrize("provider", ["openai", "anthropic"])
def test_max_retries_zero_prevents_retry(provider, monkeypatch):
    error = make_transport_error(provider, "timeout")
    monkeypatch.setenv("AI_PROVIDER_MAX_RETRIES", "0")
    invoke, sdk_calls, usage_logs, sleeps, _ = arrange_provider_call(
        provider,
        [error],
        monkeypatch,
    )

    with pytest.raises(ProviderError) as captured:
        invoke()

    assert captured.value.__cause__ is error
    assert len(sdk_calls) == 1
    assert usage_logs == []
    assert sleeps == []


@pytest.mark.parametrize("provider", ["openai", "anthropic"])
def test_default_policy_allows_two_retries_then_success(provider, monkeypatch):
    errors = [
        make_transport_error(provider, "timeout"),
        make_transport_error(provider, "connection"),
    ]
    invoke, sdk_calls, usage_logs, sleeps, _ = arrange_provider_call(
        provider,
        [*errors, success_response(provider)],
        monkeypatch,
    )

    assert invoke() == "response"
    assert len(sdk_calls) == 3
    assert len(usage_logs) == 1
    assert sleeps == [1.0, 2.0]


@pytest.mark.parametrize("provider", ["openai", "anthropic"])
def test_exhaustion_raises_last_normalized_error_with_sdk_cause(
    provider,
    monkeypatch,
):
    first = make_transport_error(provider, "timeout")
    last = make_transport_error(provider, "timeout")
    monkeypatch.setenv("AI_PROVIDER_MAX_RETRIES", "1")
    invoke, sdk_calls, usage_logs, sleeps, _ = arrange_provider_call(
        provider,
        [first, last],
        monkeypatch,
    )

    with pytest.raises(ProviderError) as captured:
        invoke()

    assert captured.value.__cause__ is last
    assert len(sdk_calls) == 2
    assert usage_logs == []
    assert sleeps == [1.0]


@pytest.mark.parametrize("provider", ["openai", "anthropic"])
def test_retry_after_has_priority_and_respects_max_delay(provider, monkeypatch):
    error = make_status_error(
        provider,
        "rate_limit",
        headers={"retry-after": "120"},
    )
    monkeypatch.setenv("AI_PROVIDER_RETRY_BASE_DELAY_SECONDS", "7")
    monkeypatch.setenv("AI_PROVIDER_RETRY_MAX_DELAY_SECONDS", "3")
    invoke, sdk_calls, usage_logs, sleeps, _ = arrange_provider_call(
        provider,
        [error, success_response(provider)],
        monkeypatch,
    )

    assert invoke() == "response"
    assert len(sdk_calls) == 2
    assert len(usage_logs) == 1
    assert sleeps == [3.0]


@pytest.mark.parametrize("provider", ["openai", "anthropic"])
def test_log_usage_failure_after_remote_success_does_not_repeat_request(
    provider,
    monkeypatch,
):
    def fail_to_log(record):
        raise RuntimeError("CSV unavailable")

    invoke, sdk_calls, _, sleeps, _ = arrange_provider_call(
        provider,
        [success_response(provider)],
        monkeypatch,
        log_usage=fail_to_log,
    )

    with pytest.raises(RuntimeError, match="CSV unavailable"):
        invoke()

    assert len(sdk_calls) == 1
    assert sleeps == []


@pytest.mark.parametrize("provider", ["openai", "anthropic"])
def test_document_call_uses_the_same_retry_policy(provider, monkeypatch):
    error = make_transport_error(provider, "timeout")
    invoke, sdk_calls, usage_logs, sleeps, _ = arrange_provider_call(
        provider,
        [error, success_response(provider)],
        monkeypatch,
        operation="document",
    )

    assert invoke() == "response"
    assert len(sdk_calls) == 2
    assert len(usage_logs) == 1
    assert sleeps == [1.0]
