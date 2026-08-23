import importlib
from pathlib import Path

import pytest

from ai_engine.models import DocumentContent

config_module = importlib.import_module("ai_engine.config")
multimodal_module = importlib.import_module("ai_engine.multimodal")
router_module = importlib.import_module("ai_engine.router")


@pytest.mark.parametrize(
    ("provider", "expected_adapter"),
    [
        ("openai", "openai"),
        ("gemini", "gemini"),
        ("google", "gemini"),
        ("anthropic", "anthropic"),
        ("claude", "anthropic"),
    ],
)
def test_ask_ai_routes_provider_and_aliases(provider, expected_adapter, monkeypatch):
    calls = []

    def make_adapter(name):
        def adapter(prompt):
            calls.append((name, prompt))
            return f"response:{name}"

        return adapter

    monkeypatch.setattr(router_module, "ask_openai", make_adapter("openai"))
    monkeypatch.setattr(router_module, "ask_gemini", make_adapter("gemini"))
    monkeypatch.setattr(router_module, "ask_anthropic", make_adapter("anthropic"))

    result = router_module.ask_ai(provider.upper(), "Hello")

    assert result == f"response:{expected_adapter}"
    assert calls == [(expected_adapter, "Hello")]


def test_ask_ai_rejects_unknown_provider():
    with pytest.raises(ValueError, match="Unknown provider: unknown"):
        router_module.ask_ai("unknown", "Hello")


@pytest.mark.parametrize(
    ("provider", "adapter_name"),
    [
        ("openai", "ask_openai"),
        ("anthropic", "ask_anthropic"),
        ("claude", "ask_anthropic"),
        ("gemini", "ask_gemini"),
        ("google", "ask_gemini"),
    ],
)
def test_ask_ai_forwards_native_structured_to_text_adapters(
    provider,
    adapter_name,
    monkeypatch,
):
    calls = []

    def adapter(prompt, *, native_structured=False):
        calls.append((prompt, native_structured))
        return "structured response"

    monkeypatch.setattr(router_module, adapter_name, adapter)

    assert router_module.ask_ai(
        provider,
        "Create output",
        native_structured=True,
    ) == "structured response"
    assert calls == [("Create output", True)]


@pytest.mark.parametrize(
    ("provider", "expected_adapter"),
    [
        ("openai", "openai"),
        ("gemini", "gemini"),
        ("google", "gemini"),
        ("anthropic", "anthropic"),
        ("claude", "anthropic"),
    ],
)
def test_ask_document_routes_provider_and_aliases(
    provider,
    expected_adapter,
    monkeypatch,
):
    document = DocumentContent(source_path=Path("document.txt"), text="Content")
    calls = []

    def make_adapter(name):
        def adapter(document, prompt):
            calls.append((name, document, prompt))
            return f"response:{name}"

        return adapter

    monkeypatch.setattr(
        multimodal_module,
        "ask_openai_document",
        make_adapter("openai"),
    )
    monkeypatch.setattr(
        multimodal_module,
        "ask_gemini_document",
        make_adapter("gemini"),
    )
    monkeypatch.setattr(
        multimodal_module,
        "ask_anthropic_document",
        make_adapter("anthropic"),
    )

    result = multimodal_module.ask_document(provider.upper(), document, "Analyze")

    assert result == f"response:{expected_adapter}"
    assert calls == [(expected_adapter, document, "Analyze")]


def test_ask_document_rejects_unknown_provider():
    document = DocumentContent(source_path=Path("document.txt"))

    with pytest.raises(ValueError, match="Unknown multimodal provider: unknown"):
        multimodal_module.ask_document("unknown", document, "Analyze")


@pytest.mark.parametrize(
    ("provider", "expected_adapter"),
    [
        ("openai", "openai"),
        ("gemini", "gemini"),
        ("google", "gemini"),
        ("anthropic", "anthropic"),
        ("claude", "anthropic"),
    ],
)
def test_native_structured_is_forwarded_only_to_native_providers(
    provider,
    expected_adapter,
    monkeypatch,
):
    document = DocumentContent(source_path=Path("document.txt"), text="Content")
    calls = []

    def fake_openai(document, prompt, *, native_structured=False):
        calls.append(("openai", native_structured))
        return "response"

    def fake_anthropic(document, prompt, *, native_structured=False):
        calls.append(("anthropic", native_structured))
        return "response"

    def fake_gemini(document, prompt, *, native_structured=False):
        calls.append(("gemini", native_structured))
        return "response"

    monkeypatch.setattr(multimodal_module, "ask_openai_document", fake_openai)
    monkeypatch.setattr(
        multimodal_module,
        "ask_gemini_document",
        fake_gemini,
    )
    monkeypatch.setattr(
        multimodal_module,
        "ask_anthropic_document",
        fake_anthropic,
    )

    multimodal_module.ask_document(
        provider,
        document,
        "Analyze",
        native_structured=True,
    )

    assert calls == [(expected_adapter, True)]


def test_load_environment_uses_project_env_file(monkeypatch):
    calls = []
    monkeypatch.setattr(config_module, "load_dotenv", lambda path: calls.append(path))

    config_module.load_environment()

    assert calls == [config_module.ENV_FILE]
