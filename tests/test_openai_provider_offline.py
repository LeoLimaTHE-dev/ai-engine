from pathlib import Path
from types import SimpleNamespace

from ai_engine.models import DocumentContent
from ai_engine.providers import openai_provider


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

    monkeypatch.setattr(openai_provider, "OpenAI", lambda: fake_client)

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
