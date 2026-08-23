import base64
import importlib
from pathlib import Path
from types import SimpleNamespace

from ai_engine.models import DocumentContent, DocumentImage
from ai_engine.usage import UsageRecord

anthropic_module = importlib.import_module("ai_engine.providers.anthropic_provider")
gemini_module = importlib.import_module("ai_engine.providers.gemini_provider")
openai_module = importlib.import_module("ai_engine.providers.openai_provider")


def make_document():
    return DocumentContent(
        source_path=Path("Painel CDC.jpeg"),
        text="Document text",
        images=[
            DocumentImage(
                name="Painel CDC.jpeg",
                data=b"original-image",
                media_type="image/jpeg",
            )
        ],
    )


def normalized_image():
    return DocumentImage(
        name="source.png",
        data=b"normalized-image",
        media_type="image/png",
    )


def test_ask_openai_builds_text_request_logs_usage_and_returns_text(monkeypatch):
    calls = []
    logs = []
    response = SimpleNamespace(
        output_text="OpenAI response",
        usage=SimpleNamespace(input_tokens=10, output_tokens=4, total_tokens=14),
    )
    client = SimpleNamespace(
        responses=SimpleNamespace(
            create=lambda **kwargs: calls.append(kwargs) or response,
        )
    )
    monkeypatch.setattr(openai_module, "OpenAI", lambda **kwargs: client)
    monkeypatch.setattr(openai_module, "log_usage", logs.append)
    monkeypatch.setenv("OPENAI_MODEL", "openai-test")

    result = openai_module.ask_openai("Hello")

    assert result == "OpenAI response"
    assert calls == [{"model": "openai-test", "input": "Hello"}]
    assert logs == [
        UsageRecord(
            provider="openai",
            model="openai-test",
            input_tokens=10,
            output_tokens=4,
            total_tokens=14,
        )
    ]


def test_ask_openai_skips_logging_without_usage(monkeypatch):
    response = SimpleNamespace(output_text="OpenAI response", usage=None)
    client = SimpleNamespace(
        responses=SimpleNamespace(create=lambda **kwargs: response)
    )
    monkeypatch.setattr(openai_module, "OpenAI", lambda **kwargs: client)

    def fail_if_called(record):
        raise AssertionError("log_usage must not run without usage")

    monkeypatch.setattr(openai_module, "log_usage", fail_if_called)

    assert openai_module.ask_openai("Hello") == "OpenAI response"


def test_ask_openai_document_builds_multimodal_payload_and_logs(monkeypatch):
    calls = []
    logs = []
    response = SimpleNamespace(
        output_text="OpenAI document response",
        usage=SimpleNamespace(input_tokens=20, output_tokens=5, total_tokens=25),
    )
    client = SimpleNamespace(
        responses=SimpleNamespace(
            create=lambda **kwargs: calls.append(kwargs) or response,
        )
    )
    monkeypatch.setattr(openai_module, "OpenAI", lambda **kwargs: client)
    monkeypatch.setattr(openai_module, "normalize_image", lambda image: normalized_image())
    monkeypatch.setattr(openai_module, "log_usage", logs.append)
    monkeypatch.setenv("OPENAI_MODEL", "openai-document-test")

    result = openai_module.ask_openai_document(make_document(), "Analyze")

    assert result == "OpenAI document response"
    assert calls[0]["model"] == "openai-document-test"
    content = calls[0]["input"][0]["content"]
    assert content[0]["type"] == "input_text"
    assert "Analyze" in content[0]["text"]
    assert "DOCUMENT CONTENT:\n\nDocument text" in content[0]["text"]
    assert content[1]["type"] == "input_text"
    assert "Painel CDC.jpeg" in content[1]["text"]
    assert content[2] == {
        "type": "input_image",
        "image_url": "data:image/png;base64,"
        + base64.b64encode(b"normalized-image").decode("utf-8"),
    }
    assert logs == [
        UsageRecord(
            provider="openai",
            model="openai-document-test",
            input_tokens=20,
            output_tokens=5,
            total_tokens=25,
        )
    ]


def gemini_usage():
    return SimpleNamespace(
        total_input_tokens=11,
        total_output_tokens=6,
        total_thought_tokens=2,
        total_cached_tokens=3,
        total_tokens=19,
    )


def test_ask_gemini_builds_text_request_logs_usage_and_returns_text(monkeypatch):
    calls = []
    logs = []
    interaction = SimpleNamespace(output_text="Gemini response", usage=gemini_usage())
    client = SimpleNamespace(
        interactions=SimpleNamespace(
            create=lambda **kwargs: calls.append(kwargs) or interaction,
        )
    )
    monkeypatch.setattr(gemini_module.genai, "Client", lambda **kwargs: client)
    monkeypatch.setattr(gemini_module, "log_usage", logs.append)
    monkeypatch.setenv("GEMINI_MODEL", "gemini-test")

    result = gemini_module.ask_gemini("Hello")

    assert result == "Gemini response"
    assert calls == [{"model": "gemini-test", "input": "Hello"}]
    assert logs == [
        UsageRecord(
            provider="gemini",
            model="gemini-test",
            input_tokens=11,
            output_tokens=6,
            thought_tokens=2,
            cached_tokens=3,
            total_tokens=19,
        )
    ]


def test_ask_gemini_document_builds_payload_and_skips_log_without_usage(monkeypatch):
    calls = []
    interaction = SimpleNamespace(
        output_text="Gemini document response",
        usage=None,
    )
    client = SimpleNamespace(
        interactions=SimpleNamespace(
            create=lambda **kwargs: calls.append(kwargs) or interaction,
        )
    )
    monkeypatch.setattr(gemini_module.genai, "Client", lambda **kwargs: client)
    monkeypatch.setattr(gemini_module, "normalize_image", lambda image: normalized_image())

    def fail_if_called(record):
        raise AssertionError("log_usage must not run without usage")

    monkeypatch.setattr(gemini_module, "log_usage", fail_if_called)
    monkeypatch.setenv("GEMINI_MODEL", "gemini-document-test")

    result = gemini_module.ask_gemini_document(make_document(), "Analyze")

    assert result == "Gemini document response"
    assert calls[0]["model"] == "gemini-document-test"
    inputs = calls[0]["input"]
    assert inputs[0]["type"] == "text"
    assert "Analyze" in inputs[0]["text"]
    assert "DOCUMENT CONTENT:\n\nDocument text" in inputs[0]["text"]
    assert inputs[1]["type"] == "text"
    assert "Painel CDC.jpeg" in inputs[1]["text"]
    assert inputs[2] == {
        "type": "image",
        "data": base64.b64encode(b"normalized-image").decode("utf-8"),
        "mime_type": "image/png",
    }


def anthropic_response(*text_parts, include_nontext=False):
    content = []
    if include_nontext:
        content.append(SimpleNamespace(type="tool", text="ignored"))
    content.extend(SimpleNamespace(type="text", text=text) for text in text_parts)
    return SimpleNamespace(
        content=content,
        usage=SimpleNamespace(input_tokens=12, output_tokens=7),
    )


def test_ask_anthropic_builds_text_request_logs_usage_and_returns_text(monkeypatch):
    calls = []
    logs = []
    response = anthropic_response("Anthropic response")
    client = SimpleNamespace(
        messages=SimpleNamespace(
            create=lambda **kwargs: calls.append(kwargs) or response,
        )
    )
    monkeypatch.setattr(anthropic_module, "Anthropic", lambda **kwargs: client)
    monkeypatch.setattr(anthropic_module, "log_usage", logs.append)
    monkeypatch.setenv("ANTHROPIC_MODEL", "claude-test")

    result = anthropic_module.ask_anthropic("Hello")

    assert result == "Anthropic response"
    assert calls == [
        {
            "model": "claude-test",
            "max_tokens": 1024,
            "messages": [{"role": "user", "content": "Hello"}],
        }
    ]
    assert logs == [
        UsageRecord(
            provider="anthropic",
            model="claude-test",
            input_tokens=12,
            output_tokens=7,
            total_tokens=19,
        )
    ]


def test_ask_anthropic_document_builds_multimodal_payload_and_joins_text(monkeypatch):
    calls = []
    logs = []
    response = anthropic_response(
        "First block",
        "Second block",
        include_nontext=True,
    )
    client = SimpleNamespace(
        messages=SimpleNamespace(
            create=lambda **kwargs: calls.append(kwargs) or response,
        )
    )
    monkeypatch.setattr(anthropic_module, "Anthropic", lambda **kwargs: client)
    monkeypatch.setattr(
        anthropic_module,
        "normalize_image",
        lambda image: normalized_image(),
    )
    monkeypatch.setattr(anthropic_module, "log_usage", logs.append)
    monkeypatch.setenv("ANTHROPIC_MODEL", "claude-document-test")

    result = anthropic_module.ask_anthropic_document(make_document(), "Analyze")

    assert result == "First block\nSecond block"
    assert calls[0]["model"] == "claude-document-test"
    assert calls[0]["max_tokens"] == 2048
    content = calls[0]["messages"][0]["content"]
    assert content[0]["type"] == "text"
    assert "Painel CDC.jpeg" in content[0]["text"]
    assert content[1] == {
        "type": "image",
        "source": {
            "type": "base64",
            "media_type": "image/png",
            "data": base64.b64encode(b"normalized-image").decode("utf-8"),
        },
    }
    assert content[2]["type"] == "text"
    assert "Analyze" in content[2]["text"]
    assert "DOCUMENT CONTENT:\n\nDocument text" in content[2]["text"]
    assert logs == [
        UsageRecord(
            provider="anthropic",
            model="claude-document-test",
            input_tokens=12,
            output_tokens=7,
            total_tokens=19,
        )
    ]
