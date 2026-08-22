import ast
from pathlib import Path
from types import SimpleNamespace

import pytest

from ai_engine import config
from ai_engine.models import DocumentContent
from ai_engine.providers import (
    anthropic_provider,
    gemini_provider,
    openai_provider,
)


@pytest.mark.parametrize("value", [None, "", "   "])
def test_provider_timeout_uses_default_when_environment_is_absent_or_empty(
    value,
    monkeypatch,
):
    if value is None:
        monkeypatch.delenv("AI_PROVIDER_TIMEOUT_SECONDS", raising=False)
    else:
        monkeypatch.setenv("AI_PROVIDER_TIMEOUT_SECONDS", value)

    assert config.get_provider_timeout_seconds() == 300


@pytest.mark.parametrize(
    ("value", "expected"),
    [("30", 30.0), ("2.5", 2.5)],
)
def test_provider_timeout_accepts_positive_integer_and_decimal(
    value,
    expected,
    monkeypatch,
):
    monkeypatch.setenv("AI_PROVIDER_TIMEOUT_SECONDS", value)

    assert config.get_provider_timeout_seconds() == expected


@pytest.mark.parametrize("value", ["0", "-1", "NaN", "Infinity", "invalid"])
def test_provider_timeout_rejects_invalid_explicit_values(value, monkeypatch):
    monkeypatch.setenv("AI_PROVIDER_TIMEOUT_SECONDS", value)

    with pytest.raises(ValueError, match="positive finite number"):
        config.get_provider_timeout_seconds()


def test_provider_timeout_observes_environment_changes_between_calls(monkeypatch):
    monkeypatch.setenv("AI_PROVIDER_TIMEOUT_SECONDS", "30")
    assert config.get_provider_timeout_seconds() == 30

    monkeypatch.setenv("AI_PROVIDER_TIMEOUT_SECONDS", "120.5")
    assert config.get_provider_timeout_seconds() == 120.5


@pytest.mark.parametrize("value", [None, "", "   "])
def test_provider_max_retries_uses_default_when_absent_or_empty(value, monkeypatch):
    if value is None:
        monkeypatch.delenv("AI_PROVIDER_MAX_RETRIES", raising=False)
    else:
        monkeypatch.setenv("AI_PROVIDER_MAX_RETRIES", value)

    assert config.get_provider_max_retries() == 2


@pytest.mark.parametrize("value", ["0", "1", "2", "5"])
def test_provider_max_retries_accepts_non_negative_integers(value, monkeypatch):
    monkeypatch.setenv("AI_PROVIDER_MAX_RETRIES", value)

    assert config.get_provider_max_retries() == int(value)


@pytest.mark.parametrize(
    "value",
    ["-1", "1.5", "abc", "NaN", "Infinity"],
)
def test_provider_max_retries_rejects_invalid_values(value, monkeypatch):
    monkeypatch.setenv("AI_PROVIDER_MAX_RETRIES", value)

    with pytest.raises(ValueError, match="non-negative integer"):
        config.get_provider_max_retries()


@pytest.mark.parametrize(
    ("environment_name", "getter", "expected"),
    [
        (
            "AI_PROVIDER_RETRY_BASE_DELAY_SECONDS",
            config.get_provider_retry_base_delay_seconds,
            1.0,
        ),
        (
            "AI_PROVIDER_RETRY_MAX_DELAY_SECONDS",
            config.get_provider_retry_max_delay_seconds,
            10.0,
        ),
    ],
)
@pytest.mark.parametrize("value", [None, "", "   "])
def test_provider_retry_delays_use_defaults_when_absent_or_empty(
    environment_name,
    getter,
    expected,
    value,
    monkeypatch,
):
    if value is None:
        monkeypatch.delenv(environment_name, raising=False)
    else:
        monkeypatch.setenv(environment_name, value)

    assert getter() == expected


@pytest.mark.parametrize(
    ("environment_name", "getter"),
    [
        (
            "AI_PROVIDER_RETRY_BASE_DELAY_SECONDS",
            config.get_provider_retry_base_delay_seconds,
        ),
        (
            "AI_PROVIDER_RETRY_MAX_DELAY_SECONDS",
            config.get_provider_retry_max_delay_seconds,
        ),
    ],
)
@pytest.mark.parametrize(
    ("value", "expected"),
    [("0", 0.0), ("2.5", 2.5)],
)
def test_provider_retry_delays_accept_finite_non_negative_numbers(
    environment_name,
    getter,
    value,
    expected,
    monkeypatch,
):
    monkeypatch.setenv(environment_name, value)

    assert getter() == expected


@pytest.mark.parametrize(
    ("environment_name", "getter"),
    [
        (
            "AI_PROVIDER_RETRY_BASE_DELAY_SECONDS",
            config.get_provider_retry_base_delay_seconds,
        ),
        (
            "AI_PROVIDER_RETRY_MAX_DELAY_SECONDS",
            config.get_provider_retry_max_delay_seconds,
        ),
    ],
)
@pytest.mark.parametrize("value", ["-1", "NaN", "Infinity", "invalid"])
def test_provider_retry_delays_reject_invalid_values(
    environment_name,
    getter,
    value,
    monkeypatch,
):
    monkeypatch.setenv(environment_name, value)

    with pytest.raises(ValueError, match="finite non-negative number"):
        getter()


def test_provider_retry_configuration_observes_environment_changes(monkeypatch):
    monkeypatch.setenv("AI_PROVIDER_MAX_RETRIES", "0")
    monkeypatch.setenv("AI_PROVIDER_RETRY_BASE_DELAY_SECONDS", "0.5")
    monkeypatch.setenv("AI_PROVIDER_RETRY_MAX_DELAY_SECONDS", "3")

    assert config.get_provider_max_retries() == 0
    assert config.get_provider_retry_base_delay_seconds() == 0.5
    assert config.get_provider_retry_max_delay_seconds() == 3

    monkeypatch.setenv("AI_PROVIDER_MAX_RETRIES", "5")
    monkeypatch.setenv("AI_PROVIDER_RETRY_BASE_DELAY_SECONDS", "12")
    monkeypatch.setenv("AI_PROVIDER_RETRY_MAX_DELAY_SECONDS", "4")

    assert config.get_provider_max_retries() == 5
    assert config.get_provider_retry_base_delay_seconds() == 12
    assert config.get_provider_retry_max_delay_seconds() == 4


def make_document():
    return DocumentContent(source_path=Path("document.txt"), text="Content")


def openai_response():
    return SimpleNamespace(output_text="response", usage=None)


@pytest.mark.parametrize("operation", ["text", "document"])
def test_openai_client_receives_timeout_and_zero_native_retries(
    operation,
    monkeypatch,
):
    client_calls = []
    client = SimpleNamespace(
        responses=SimpleNamespace(create=lambda **kwargs: openai_response()),
    )

    def make_client(**kwargs):
        client_calls.append(kwargs)
        return client

    monkeypatch.setenv("AI_PROVIDER_TIMEOUT_SECONDS", "2.5")
    monkeypatch.setattr(openai_provider, "OpenAI", make_client)

    if operation == "text":
        openai_provider.ask_openai("Hello")
    else:
        openai_provider.ask_openai_document(make_document(), "Analyze")

    assert client_calls == [{"timeout": 2.5, "max_retries": 0}]


def anthropic_response():
    return SimpleNamespace(
        content=[SimpleNamespace(type="text", text="response")],
        usage=SimpleNamespace(input_tokens=0, output_tokens=0),
    )


@pytest.mark.parametrize("operation", ["text", "document"])
def test_anthropic_client_receives_timeout_and_zero_native_retries(
    operation,
    monkeypatch,
):
    client_calls = []
    client = SimpleNamespace(
        messages=SimpleNamespace(create=lambda **kwargs: anthropic_response()),
    )

    def make_client(**kwargs):
        client_calls.append(kwargs)
        return client

    monkeypatch.setenv("AI_PROVIDER_TIMEOUT_SECONDS", "2.5")
    monkeypatch.setattr(anthropic_provider, "Anthropic", make_client)
    monkeypatch.setattr(anthropic_provider, "log_usage", lambda record: None)

    if operation == "text":
        anthropic_provider.ask_anthropic("Hello")
    else:
        anthropic_provider.ask_anthropic_document(make_document(), "Analyze")

    assert client_calls == [{"timeout": 2.5, "max_retries": 0}]


def gemini_response():
    return SimpleNamespace(output_text="response", usage=None)


@pytest.mark.parametrize("operation", ["text", "document"])
def test_gemini_client_receives_millisecond_timeout_without_unsupported_retry_override(
    operation,
    monkeypatch,
):
    client_calls = []
    client = SimpleNamespace(
        interactions=SimpleNamespace(create=lambda **kwargs: gemini_response()),
    )

    def make_client(**kwargs):
        client_calls.append(kwargs)
        return client

    monkeypatch.setenv("AI_PROVIDER_TIMEOUT_SECONDS", "2.5")
    monkeypatch.setattr(gemini_provider.genai, "Client", make_client)

    if operation == "text":
        gemini_provider.ask_gemini("Hello")
    else:
        gemini_provider.ask_gemini_document(make_document(), "Analyze")

    assert len(client_calls) == 1
    http_options = client_calls[0]["http_options"]
    assert http_options.timeout == 2500
    assert http_options.retry_options is None


def test_gemini_adapter_does_not_use_common_retry_helper():
    provider_file = "gemini_provider.py"
    source_path = (
        Path(__file__).parents[1]
        / "src"
        / "ai_engine"
        / "providers"
        / provider_file
    )
    tree = ast.parse(source_path.read_text(encoding="utf-8"))

    imported_names = {
        alias.name
        for node in ast.walk(tree)
        if isinstance(node, (ast.Import, ast.ImportFrom))
        for alias in node.names
    }
    called_names = {
        node.func.id
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
    }

    assert "retry_provider_call" not in imported_names
    assert "retry_provider_call" not in called_names
