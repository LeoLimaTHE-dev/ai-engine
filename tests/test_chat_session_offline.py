import importlib
from pathlib import Path

import pytest

from ai_engine import ProviderRateLimitError

from ai_engine.models import DocumentContent
from ai_engine.results import OutputRequest, StructuredResult
from ai_engine.session import ConversationMessage, ConversationSession

chat_module = importlib.import_module("ai_engine.chat")
workflow_module = importlib.import_module("ai_engine.workflow")


def make_documents():
    return [
        DocumentContent(
            source_path=Path("document.txt"),
            text="Document content",
        )
    ]


def make_session(**kwargs):
    return ConversationSession(
        provider="openai",
        documents=make_documents(),
        **kwargs,
    )


def test_conversation_message_preserves_role_and_content():
    message = ConversationMessage(role="user", content="Hello")

    assert message.role == "user"
    assert message.content == "Hello"


def test_session_adds_user_and_assistant_messages_in_order():
    session = make_session()

    session.add_user_message("Question")
    session.add_assistant_message("Answer")

    assert session.messages == [
        ConversationMessage(role="user", content="Question"),
        ConversationMessage(role="assistant", content="Answer"),
    ]
    assert session.message_count == 2


def test_session_moves_old_messages_to_pending_summary_at_history_limit():
    session = make_session(max_history_messages=2, summary_batch_size=2)

    session.add_user_message("Question 1")
    session.add_assistant_message("Answer 1")
    session.add_user_message("Question 2")

    assert session.messages == [
        ConversationMessage(role="assistant", content="Answer 1"),
        ConversationMessage(role="user", content="Question 2"),
    ]
    assert session.pending_summary == [
        ConversationMessage(role="user", content="Question 1")
    ]
    assert session.should_update_summary is False

    session.add_assistant_message("Answer 2")

    assert session.messages == [
        ConversationMessage(role="user", content="Question 2"),
        ConversationMessage(role="assistant", content="Answer 2"),
    ]
    assert session.pending_summary == [
        ConversationMessage(role="user", content="Question 1"),
        ConversationMessage(role="assistant", content="Answer 1"),
    ]
    assert session.should_update_summary is True


def test_get_pending_summary_text_labels_each_role():
    session = make_session()
    session.pending_summary = [
        ConversationMessage(role="user", content="Old question"),
        ConversationMessage(role="assistant", content="Old answer"),
    ]

    assert session.get_pending_summary_text() == (
        "USER:\nOld question\n\nASSISTANT:\nOld answer"
    )


def test_apply_summary_strips_summary_and_clears_pending_messages():
    session = make_session()
    session.pending_summary = [ConversationMessage(role="user", content="Old")]

    session.apply_summary("  Compact memory  ")

    assert session.summary == "Compact memory"
    assert session.pending_summary == []


def test_clear_history_clears_all_textual_memory():
    session = make_session()
    session.summary = "Summary"
    session.messages = [ConversationMessage(role="user", content="Recent")]
    session.pending_summary = [ConversationMessage(role="assistant", content="Old")]

    session.clear_history()

    assert session.summary == ""
    assert session.messages == []
    assert session.pending_summary == []


def test_build_conversation_prompt_includes_summary_history_and_current_request():
    session = make_session()
    session.summary = "Earlier facts"
    session.messages = [
        ConversationMessage(role="user", content="Previous question"),
        ConversationMessage(role="assistant", content="Previous answer"),
    ]

    prompt = session.build_conversation_prompt("Current question")

    assert prompt == (
        "SUMMARY OF EARLIER CONVERSATION:\n\n"
        "Earlier facts\n\n"
        "RECENT CONVERSATION:\n\n"
        "USER:\nPrevious question\n\n"
        "ASSISTANT:\nPrevious answer\n\n"
        "CURRENT USER REQUEST:\n\n"
        "Current question"
    )


def test_change_provider_preserves_all_context_by_default():
    session = make_session()
    session.summary = "Summary"
    session.messages = [ConversationMessage(role="user", content="Recent")]
    session.pending_summary = [ConversationMessage(role="assistant", content="Old")]
    original_documents = session.documents

    session.change_provider("claude", keep_history=True)

    assert session.provider == "claude"
    assert session.summary == "Summary"
    assert session.messages == [ConversationMessage(role="user", content="Recent")]
    assert session.pending_summary == [
        ConversationMessage(role="assistant", content="Old")
    ]
    assert session.documents is original_documents


@pytest.mark.parametrize(
    ("provider", "expected"),
    [
        ("google", "gemini"),
        ("anthropic", "claude"),
    ],
)
def test_change_provider_normalizes_aliases(provider, expected):
    session = make_session()

    session.change_provider(provider)

    assert session.provider == expected


def test_change_provider_without_history_clears_memory_but_keeps_documents():
    session = make_session()
    session.summary = "Summary"
    session.messages = [ConversationMessage(role="user", content="Recent")]
    session.pending_summary = [ConversationMessage(role="assistant", content="Old")]
    original_documents = session.documents

    session.change_provider("gemini", keep_history=False)

    assert session.provider == "gemini"
    assert session.summary == ""
    assert session.messages == []
    assert session.pending_summary == []
    assert session.documents is original_documents


def test_change_provider_rejects_invalid_provider():
    session = make_session()

    with pytest.raises(ValueError, match="Unsupported provider: invalid"):
        session.change_provider("invalid")


def test_build_summary_prompt_is_empty_before_batch_is_ready():
    session = make_session(summary_batch_size=2)
    session.pending_summary = [ConversationMessage(role="user", content="Only one")]

    assert chat_module.build_summary_prompt(session) == ""


def test_build_summary_prompt_combines_existing_summary_and_pending_messages():
    session = make_session(summary_batch_size=2)
    session.summary = "Existing memory"
    session.pending_summary = [
        ConversationMessage(role="user", content="Old question"),
        ConversationMessage(role="assistant", content="Old answer"),
    ]

    prompt = chat_module.build_summary_prompt(session)

    assert prompt.startswith(chat_module.SUMMARY_INSTRUCTIONS)
    assert "EXISTING SUMMARY:\nExisting memory" in prompt
    assert "NEW OLDER MESSAGES:" in prompt
    assert "USER:\nOld question" in prompt
    assert "ASSISTANT:\nOld answer" in prompt


def test_summarize_session_does_nothing_before_batch_is_ready(monkeypatch):
    session = make_session(summary_batch_size=2)
    session.pending_summary = [ConversationMessage(role="user", content="Only one")]

    def fail_if_called(**kwargs):
        raise AssertionError("ask_ai must not run before summary batch is ready")

    monkeypatch.setattr(chat_module, "ask_ai", fail_if_called)

    assert chat_module.summarize_session(session) is None
    assert session.pending_summary == [
        ConversationMessage(role="user", content="Only one")
    ]


def test_summarize_session_uses_provider_and_clears_pending_summary(monkeypatch):
    session = make_session(summary_batch_size=2)
    session.prompt_template = "resumir.md"
    session.pending_summary = [
        ConversationMessage(role="user", content="Old question"),
        ConversationMessage(role="assistant", content="Old answer"),
    ]
    calls = []

    def fake_ask_ai(**kwargs):
        calls.append(kwargs)
        return "  Updated compact memory  "

    monkeypatch.setattr(chat_module, "ask_ai", fake_ask_ai)

    result = chat_module.summarize_session(session)

    assert result == "  Updated compact memory  "
    assert len(calls) == 1
    assert calls[0]["provider"] == "openai"
    assert "Old question" in calls[0]["prompt"]
    assert "prompt_template" not in calls[0]
    assert session.summary == "Updated compact memory"
    assert session.pending_summary == []


def test_chat_adds_current_turn_only_after_successful_workflow(monkeypatch):
    session = make_session()
    session.add_user_message("Earlier question")
    session.add_assistant_message("Earlier answer")
    calls = []

    def fake_workflow(**kwargs):
        calls.append(kwargs)
        assert session.messages == [
            ConversationMessage(role="user", content="Earlier question"),
            ConversationMessage(role="assistant", content="Earlier answer"),
        ]
        return StructuredResult(message="Current answer")

    monkeypatch.setattr(
        chat_module,
        "run_structured_workflow_documents",
        fake_workflow,
    )

    result = chat_module.chat(session, "  Current question  ")

    assert result == StructuredResult(message="Current answer")
    assert calls[0]["provider"] == "openai"
    assert calls[0]["documents"] is session.documents
    assert calls[0]["mode"] == "auto"
    assert calls[0]["prompt_template"] is None
    assert "CURRENT USER REQUEST:\n\nCurrent question" in calls[0]["user_prompt"]
    assert session.messages[-2:] == [
        ConversationMessage(role="user", content="Current question"),
        ConversationMessage(role="assistant", content="Current answer"),
    ]


def test_chat_forwards_session_prompt_template_to_workflow(monkeypatch):
    session = make_session()
    session.prompt_template = "analisar_documentos.md"
    calls = []

    monkeypatch.setattr(
        chat_module,
        "run_structured_workflow_documents",
        lambda **kwargs: calls.append(kwargs) or StructuredResult(message="Answer"),
    )

    chat_module.chat(session, "Analyze")

    assert calls[0]["prompt_template"] == "analisar_documentos.md"


def test_chat_template_is_loaded_by_the_workflow(monkeypatch, tmp_path):
    prompts_dir = tmp_path / "4_Prompts"
    prompts_dir.mkdir()
    (prompts_dir / "analysis.md").write_text(
        "# Analysis\n"
        "> Descrição: Menu metadata.\n\n"
        "EFFECTIVE TEMPLATE INSTRUCTIONS",
        encoding="utf-8",
    )
    monkeypatch.setenv("IA_ROOT", str(tmp_path))
    session = make_session(prompt_template="analysis.md")
    calls = []

    monkeypatch.setattr(
        workflow_module,
        "ask_document",
        lambda **kwargs: calls.append(kwargs) or "Normal answer",
    )

    result = chat_module.chat(session, "Analyze")

    assert result.message == "Normal answer"
    assert "EFFECTIVE TEMPLATE INSTRUCTIONS" in calls[0]["prompt"]
    assert "Menu metadata" not in calls[0]["prompt"]


def test_missing_session_template_fails_before_provider_call(monkeypatch, tmp_path):
    (tmp_path / "4_Prompts").mkdir()
    monkeypatch.setenv("IA_ROOT", str(tmp_path))
    session = make_session(prompt_template="missing.md")

    monkeypatch.setattr(
        workflow_module,
        "ask_document",
        lambda **kwargs: pytest.fail("provider adapter must not be called"),
    )

    with pytest.raises(FileNotFoundError, match="Prompt not found: missing.md"):
        chat_module.chat(session, "Analyze")


@pytest.mark.parametrize(
    "failure",
    [
        RuntimeError("workflow failed"),
        ProviderRateLimitError(
            provider="gemini",
            message="opaque",
            retryable=False,
        ),
    ],
)
def test_chat_does_not_add_current_message_when_workflow_raises(
    failure,
    monkeypatch,
):
    session = make_session()
    session.add_user_message("Existing")
    original_messages = list(session.messages)

    def failing_workflow(**kwargs):
        raise failure

    monkeypatch.setattr(
        chat_module,
        "run_structured_workflow_documents",
        failing_workflow,
    )

    with pytest.raises(type(failure)) as captured:
        chat_module.chat(session, "Current")

    assert captured.value is failure
    assert session.messages == original_messages


def test_chat_does_not_store_structured_outputs_as_assistant_text(monkeypatch):
    session = make_session()
    structured_result = StructuredResult(
        message="",
        outputs=[OutputRequest(format="txt", filename="result.txt", content="Data")],
    )

    monkeypatch.setattr(
        chat_module,
        "run_structured_workflow_documents",
        lambda **kwargs: structured_result,
    )

    result = chat_module.chat(session, "Create a file")

    assert result is structured_result
    assert session.messages == [
        ConversationMessage(role="user", content="Create a file")
    ]


def test_chat_preserves_context_between_successive_turns(monkeypatch):
    session = make_session()
    prompts = []
    responses = iter(["First answer", "Second answer"])

    def fake_workflow(**kwargs):
        prompts.append(kwargs["user_prompt"])
        return StructuredResult(message=next(responses))

    monkeypatch.setattr(
        chat_module,
        "run_structured_workflow_documents",
        fake_workflow,
    )

    chat_module.chat(session, "First question")
    chat_module.chat(session, "Second question")

    assert "First question" not in prompts[0].split("CURRENT USER REQUEST:")[0]
    assert "RECENT CONVERSATION:" in prompts[1]
    assert "USER:\nFirst question" in prompts[1]
    assert "ASSISTANT:\nFirst answer" in prompts[1]
    assert "CURRENT USER REQUEST:\n\nSecond question" in prompts[1]


def test_chat_rejects_empty_message_without_calling_workflow(monkeypatch):
    session = make_session()

    def fail_if_called(**kwargs):
        raise AssertionError("workflow must not run for an empty message")

    monkeypatch.setattr(
        chat_module,
        "run_structured_workflow_documents",
        fail_if_called,
    )

    with pytest.raises(ValueError, match="The message cannot be empty"):
        chat_module.chat(session, "   ")
