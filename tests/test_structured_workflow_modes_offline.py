import importlib
import json
from pathlib import Path

import pytest

from ai_engine.models import DocumentContent
from ai_engine.results import OutputRequest, StructuredResult
from ai_engine.session import ConversationMessage, ConversationSession
from ai_engine.structured_errors import OutputValidationError, StructuredParseError


workflow_module = importlib.import_module("ai_engine.workflow")
chat_module = importlib.import_module("ai_engine.chat")


def document(name="document.txt"):
    return DocumentContent(source_path=Path(name), text="content")


def run_single_document(monkeypatch, response, **kwargs):
    monkeypatch.setattr(
        workflow_module,
        "ask_document",
        lambda **call_kwargs: response,
    )
    return workflow_module.run_structured_workflow_documents(
        provider="openai",
        documents=[document()],
        user_prompt="Analyze",
        **kwargs,
    )


def test_structured_workflow_default_uses_legacy_parser_mode(monkeypatch):
    result = run_single_document(monkeypatch, "Normal textual response")

    assert result == StructuredResult(message="Normal textual response")


def test_explicit_false_is_equivalent_to_workflow_default(monkeypatch):
    default_result = run_single_document(monkeypatch, "Normal textual response")
    explicit_result = run_single_document(
        monkeypatch,
        "Normal textual response",
        expect_outputs=False,
    )

    assert explicit_result == default_result


def test_strong_workflow_accepts_valid_json(monkeypatch):
    response = json.dumps(
        {
            "message": "Created",
            "outputs": [
                {"format": "txt", "filename": "result.txt", "content": "Body"}
            ],
        }
    )

    result = run_single_document(monkeypatch, response, expect_outputs=True)

    assert result == StructuredResult(
        message="Created",
        outputs=[OutputRequest(format="txt", filename="result.txt", content="Body")],
    )


@pytest.mark.parametrize(
    ("provider", "expect_outputs", "expected_native"),
    [
        ("openai", True, True),
        ("OPENAI", True, True),
        ("openai", False, False),
        ("anthropic", True, True),
        ("claude", True, True),
        ("anthropic", False, False),
        ("gemini", True, False),
        ("google", True, False),
    ],
)
def test_native_structured_activation_depends_only_on_supported_provider_and_flag(
    provider,
    expect_outputs,
    expected_native,
    monkeypatch,
):
    calls = []
    response = '{"message": "Done", "outputs": []}'

    def fake_ask_document(**kwargs):
        calls.append(kwargs)
        return response if expect_outputs else "Normal response"

    monkeypatch.setattr(workflow_module, "ask_document", fake_ask_document)

    result = workflow_module.run_structured_workflow_documents(
        provider=provider,
        documents=[document()],
        user_prompt="Olá",
        expect_outputs=expect_outputs,
    )

    assert calls[0]["native_structured"] is expected_native
    assert isinstance(result, StructuredResult)


def test_anthropic_native_response_still_uses_strong_parser(monkeypatch):
    response = json.dumps(
        {
            "message": "Created",
            "outputs": [
                {"format": "txt", "filename": "result.txt", "content": "Body"}
            ],
        }
    )

    def fake_ask_document(**kwargs):
        assert kwargs["native_structured"] is True
        return response

    monkeypatch.setattr(workflow_module, "ask_document", fake_ask_document)

    result = workflow_module.run_structured_workflow_documents(
        provider="anthropic",
        documents=[document()],
        user_prompt="Analyze",
        expect_outputs=True,
    )

    assert result == StructuredResult(
        message="Created",
        outputs=[OutputRequest(format="txt", filename="result.txt", content="Body")],
    )


def test_anthropic_native_invalid_json_still_raises_parse_error(monkeypatch):
    def fake_ask_document(**kwargs):
        assert kwargs["native_structured"] is True
        return "not JSON"

    monkeypatch.setattr(workflow_module, "ask_document", fake_ask_document)

    with pytest.raises(StructuredParseError):
        workflow_module.run_structured_workflow_documents(
            provider="anthropic",
            documents=[document()],
            user_prompt="Analyze",
            expect_outputs=True,
        )


@pytest.mark.parametrize(
    "response",
    [
        "Normal textual response",
        "{invalid}",
        '```json\n{"message": "fenced"}\n```',
    ],
    ids=["text", "invalid-json", "fenced-json"],
)
def test_strong_workflow_propagates_parse_error(response, monkeypatch):
    with pytest.raises(StructuredParseError):
        run_single_document(monkeypatch, response, expect_outputs=True)


def test_strong_workflow_propagates_validation_error(monkeypatch):
    response = json.dumps(
        {
            "outputs": [
                {"format": "csv", "filename": "invalid.csv", "content": "Body"}
            ]
        }
    )

    with pytest.raises(OutputValidationError) as captured:
        run_single_document(monkeypatch, response, expect_outputs=True)

    assert captured.value.field_path == "outputs[0].format"


def test_strong_workflow_accepts_empty_outputs(monkeypatch):
    response = json.dumps({"message": "Could not create", "outputs": []})

    result = run_single_document(monkeypatch, response, expect_outputs=True)

    assert result == StructuredResult(message="Could not create", outputs=[])


def test_consolidated_branch_forwards_strong_mode(monkeypatch):
    monkeypatch.setattr(
        workflow_module,
        "process_batch_consolidated",
        lambda **kwargs: "not JSON",
    )

    with pytest.raises(StructuredParseError):
        workflow_module.run_structured_workflow_documents(
            provider="openai",
            documents=[document("one.txt"), document("two.txt")],
            user_prompt="Analyze",
            expect_outputs=True,
        )


def test_consolidated_openai_forwards_native_structured(monkeypatch):
    calls = []

    def fake_consolidated(**kwargs):
        calls.append(kwargs)
        return '{"message": "Done", "outputs": []}'

    monkeypatch.setattr(
        workflow_module,
        "process_batch_consolidated",
        fake_consolidated,
    )

    workflow_module.run_structured_workflow_documents(
        provider="openai",
        documents=[document("one.txt"), document("two.txt")],
        user_prompt="Analyze",
        expect_outputs=True,
    )

    assert calls[0]["native_structured"] is True


@pytest.mark.parametrize("provider", ["anthropic", "claude"])
def test_consolidated_anthropic_forwards_native_structured(provider, monkeypatch):
    calls = []

    def fake_consolidated(**kwargs):
        calls.append(kwargs)
        return '{"message": "Done", "outputs": []}'

    monkeypatch.setattr(
        workflow_module,
        "process_batch_consolidated",
        fake_consolidated,
    )

    workflow_module.run_structured_workflow_documents(
        provider=provider,
        documents=[document("one.txt"), document("two.txt")],
        user_prompt="Analyze",
        expect_outputs=True,
    )

    assert calls[0]["native_structured"] is True


def test_multiple_individual_branch_forwards_strong_mode(monkeypatch):
    monkeypatch.setattr(
        workflow_module,
        "process_batch_individual",
        lambda **kwargs: {"one.txt": '{"message": "ok"}', "two.txt": "not JSON"},
    )

    with pytest.raises(StructuredParseError):
        workflow_module.run_structured_workflow_documents(
            provider="openai",
            documents=[document("one.txt"), document("two.txt")],
            user_prompt="Analyze",
            mode="individual",
            expect_outputs=True,
        )


def test_multiple_individual_openai_forwards_native_structured(monkeypatch):
    calls = []

    def fake_individual(**kwargs):
        calls.append(kwargs)
        return {
            "one.txt": '{"message": "one", "outputs": []}',
            "two.txt": '{"message": "two", "outputs": []}',
        }

    monkeypatch.setattr(
        workflow_module,
        "process_batch_individual",
        fake_individual,
    )

    workflow_module.run_structured_workflow_documents(
        provider="openai",
        documents=[document("one.txt"), document("two.txt")],
        user_prompt="Analyze",
        mode="individual",
        expect_outputs=True,
    )

    assert calls[0]["native_structured"] is True


@pytest.mark.parametrize("provider", ["anthropic", "claude"])
def test_multiple_individual_anthropic_forwards_native_structured(
    provider,
    monkeypatch,
):
    calls = []

    def fake_individual(**kwargs):
        calls.append(kwargs)
        return {
            "one.txt": '{"message": "one", "outputs": []}',
            "two.txt": '{"message": "two", "outputs": []}',
        }

    monkeypatch.setattr(
        workflow_module,
        "process_batch_individual",
        fake_individual,
    )

    workflow_module.run_structured_workflow_documents(
        provider=provider,
        documents=[document("one.txt"), document("two.txt")],
        user_prompt="Analyze",
        mode="individual",
        expect_outputs=True,
    )

    assert calls[0]["native_structured"] is True


def test_path_loading_workflow_forwards_explicit_intention(monkeypatch):
    documents = [document()]
    calls = []
    monkeypatch.setattr(workflow_module, "load_documents", lambda input_path: documents)

    def fake_structured_workflow_documents(**kwargs):
        calls.append(kwargs)
        return StructuredResult(message="Done")

    monkeypatch.setattr(
        workflow_module,
        "run_structured_workflow_documents",
        fake_structured_workflow_documents,
    )

    result = workflow_module.run_structured_workflow(
        provider="openai",
        input_path="input",
        user_prompt="Analyze",
        expect_outputs=True,
    )

    assert result == StructuredResult(message="Done")
    assert calls[0]["expect_outputs"] is True


def session_with_history():
    session = ConversationSession(provider="openai", documents=[document()])
    session.summary = "Existing summary"
    session.messages = [ConversationMessage(role="assistant", content="Previous")]
    session.pending_summary = [ConversationMessage(role="user", content="Older")]
    return session


def test_chat_default_forwards_false_and_preserves_normal_behavior(monkeypatch):
    session = session_with_history()
    calls = []

    def fake_workflow(**kwargs):
        calls.append(kwargs)
        return StructuredResult(message="Answer")

    monkeypatch.setattr(chat_module, "run_structured_workflow_documents", fake_workflow)

    result = chat_module.chat(session, "Question")

    assert result == StructuredResult(message="Answer")
    assert calls[0]["expect_outputs"] is False
    assert session.messages[-2:] == [
        ConversationMessage(role="user", content="Question"),
        ConversationMessage(role="assistant", content="Answer"),
    ]


def test_chat_explicit_true_is_forwarded_and_success_adds_messages(monkeypatch):
    session = session_with_history()
    calls = []
    result = StructuredResult(
        message="Created",
        outputs=[OutputRequest(format="txt", filename="result.txt", content="Body")],
    )

    def fake_workflow(**kwargs):
        calls.append(kwargs)
        return result

    monkeypatch.setattr(chat_module, "run_structured_workflow_documents", fake_workflow)

    assert chat_module.chat(session, "Request", expect_outputs=True) is result
    assert calls[0]["expect_outputs"] is True
    assert session.messages[-2:] == [
        ConversationMessage(role="user", content="Request"),
        ConversationMessage(role="assistant", content="Created"),
    ]


@pytest.mark.parametrize(
    "failure",
    [StructuredParseError("invalid JSON"), OutputValidationError("invalid contract")],
)
def test_chat_structured_failure_preserves_all_existing_session_state(
    failure,
    monkeypatch,
):
    session = session_with_history()
    original_documents = session.documents
    original_messages = list(session.messages)
    original_pending = list(session.pending_summary)

    def failing_workflow(**kwargs):
        assert kwargs["expect_outputs"] is True
        raise failure

    monkeypatch.setattr(chat_module, "run_structured_workflow_documents", failing_workflow)

    with pytest.raises(type(failure)) as captured:
        chat_module.chat(session, "Current", expect_outputs=True)

    assert captured.value is failure
    assert session.documents is original_documents
    assert session.messages == original_messages
    assert session.pending_summary == original_pending
    assert session.summary == "Existing summary"


def test_file_words_do_not_enable_strong_mode_without_explicit_flag(monkeypatch):
    session = session_with_history()
    calls = []

    def fake_workflow(**kwargs):
        calls.append(kwargs)
        return StructuredResult(message="Text fallback")

    monkeypatch.setattr(chat_module, "run_structured_workflow_documents", fake_workflow)

    result = chat_module.chat(
        session,
        "gere um arquivo DOCX",
        expect_outputs=False,
    )

    assert result.message == "Text fallback"
    assert calls[0]["expect_outputs"] is False


def test_unrelated_words_still_enable_strong_mode_when_flag_is_true(monkeypatch):
    session = session_with_history()

    def fake_workflow(**kwargs):
        assert kwargs["expect_outputs"] is True
        raise StructuredParseError("structured output required")

    monkeypatch.setattr(chat_module, "run_structured_workflow_documents", fake_workflow)

    with pytest.raises(StructuredParseError):
        chat_module.chat(session, "Olá", expect_outputs=True)
