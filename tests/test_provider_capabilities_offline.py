import pytest

from ai_engine.provider_capabilities import (
    get_configured_document_model,
    normalize_provider,
    supports_native_structured_output,
)


@pytest.mark.parametrize(
    ("provider", "model"),
    [
        ("openai", "gpt-5"),
        ("anthropic", "claude-sonnet-5"),
        ("claude", "claude-sonnet-5"),
        ("gemini", "gemini-3.5-flash"),
        ("google", "gemini-3.5-flash"),
    ],
)
def test_locally_proven_models_support_native_structured_output(provider, model):
    assert supports_native_structured_output(provider, model) is True


@pytest.mark.parametrize(
    ("provider", "model"),
    [
        ("openai", "gpt-future"),
        ("anthropic", "claude-future"),
        ("gemini", "gemini-future"),
        ("unknown", "gpt-5"),
        ("openai", None),
    ],
)
def test_unknown_provider_or_model_does_not_support_native_structured_output(
    provider,
    model,
):
    assert supports_native_structured_output(provider, model) is False


@pytest.mark.parametrize(
    ("alias", "normalized"),
    [
        ("OPENAI", "openai"),
        ("anthropic", "anthropic"),
        ("CLAUDE", "anthropic"),
        ("gemini", "gemini"),
        ("GOOGLE", "gemini"),
        ("unknown", None),
    ],
)
def test_provider_aliases_are_normalized(alias, normalized):
    assert normalize_provider(alias) == normalized


@pytest.mark.parametrize(
    ("provider", "environment_name", "supported_model", "unknown_model"),
    [
        ("openai", "OPENAI_MODEL", "gpt-5", "gpt-future"),
        (
            "anthropic",
            "ANTHROPIC_MODEL",
            "claude-sonnet-5",
            "claude-future",
        ),
        ("gemini", "GEMINI_MODEL", "gemini-3.5-flash", "gemini-future"),
    ],
)
def test_environment_changes_capability_dynamically(
    provider,
    environment_name,
    supported_model,
    unknown_model,
    monkeypatch,
):
    monkeypatch.setenv(environment_name, supported_model)
    configured = get_configured_document_model(provider)
    assert configured == supported_model
    assert supports_native_structured_output(provider, configured) is True

    monkeypatch.setenv(environment_name, unknown_model)
    configured = get_configured_document_model(provider)
    assert configured == unknown_model
    assert supports_native_structured_output(provider, configured) is False


@pytest.mark.parametrize(
    ("provider", "environment_name", "default_model"),
    [
        ("openai", "OPENAI_MODEL", "gpt-5.6"),
        ("anthropic", "ANTHROPIC_MODEL", "claude-sonnet-5"),
        ("gemini", "GEMINI_MODEL", "gemini-3.7-flash"),
    ],
)
def test_document_model_defaults_match_adapter_defaults(
    provider,
    environment_name,
    default_model,
    monkeypatch,
):
    monkeypatch.delenv(environment_name, raising=False)

    assert get_configured_document_model(provider) == default_model


def test_unknown_provider_has_no_configured_document_model():
    assert get_configured_document_model("unknown") is None
