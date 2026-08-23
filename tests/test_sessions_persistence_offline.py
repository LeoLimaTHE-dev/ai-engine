from pathlib import Path

import pytest

from ai_engine.models import DocumentContent
from ai_engine.session import ConversationMessage, ConversationSession
from ai_engine.sessions import (
    delete_session,
    get_session_path,
    list_sessions,
    load_session_data,
    restore_conversation_session,
    sanitize_session_name,
    save_session,
)


@pytest.mark.parametrize(
    ("name", "expected"),
    [
        ("  Session 2026  ", "Session_2026"),
        ("project/report:final", "project_report_final"),
    ],
)
def test_sanitize_session_name_replaces_unsafe_characters(name, expected):
    assert sanitize_session_name(name) == expected


@pytest.mark.parametrize("name", ["", "   "])
def test_sanitize_session_name_rejects_empty_name(name):
    with pytest.raises(ValueError, match="Session name cannot be empty"):
        sanitize_session_name(name)


def test_get_session_path_uses_sanitized_name_inside_requested_directory(tmp_path):
    assert get_session_path("My Session", sessions_dir=tmp_path) == (
        tmp_path / "My_Session.json"
    )


def test_session_persistence_round_trip_restores_all_textual_state(tmp_path):
    documents = [
        DocumentContent(source_path=Path("input.txt"), text="Document content")
    ]
    session = ConversationSession(
        provider="claude",
        documents=documents,
        prompt_template="analisar_documentos.md",
        max_history_messages=6,
        summary_batch_size=2,
    )
    session.summary = "Compact memory"
    session.messages = [
        ConversationMessage(role="user", content="Recent question"),
        ConversationMessage(role="assistant", content="Recent answer"),
    ]
    session.pending_summary = [
        ConversationMessage(role="user", content="Older question")
    ]
    input_path = tmp_path / "inputs"

    saved_path = save_session(
        name="Session 1",
        session=session,
        input_path=input_path,
        sessions_dir=tmp_path,
    )
    data = load_session_data("Session 1", sessions_dir=tmp_path)
    restored = restore_conversation_session(data, documents=documents)

    assert saved_path == tmp_path / "Session_1.json"
    assert data == {
        "name": "Session 1",
        "provider": "claude",
        "prompt_template": "analisar_documentos.md",
        "input_path": str(input_path),
        "summary": "Compact memory",
        "max_history_messages": 6,
        "summary_batch_size": 2,
        "messages": [
            {"role": "user", "content": "Recent question"},
            {"role": "assistant", "content": "Recent answer"},
        ],
        "pending_summary": [
            {"role": "user", "content": "Older question"}
        ],
    }
    assert restored.provider == "claude"
    assert restored.prompt_template == "analisar_documentos.md"
    assert restored.documents is documents
    assert restored.summary == "Compact memory"
    assert restored.max_history_messages == 6
    assert restored.summary_batch_size == 2
    assert restored.messages == session.messages
    assert restored.pending_summary == session.pending_summary


def test_new_session_defaults_to_no_prompt_template():
    session = ConversationSession(provider="openai", documents=[])

    assert session.prompt_template is None


def test_session_serializes_none_prompt_template(tmp_path):
    session = ConversationSession(provider="openai", documents=[])

    save_session(
        name="No template",
        session=session,
        input_path=tmp_path / "input",
        sessions_dir=tmp_path,
    )

    assert load_session_data("No template", sessions_dir=tmp_path)[
        "prompt_template"
    ] is None


def test_old_session_without_prompt_template_restores_with_none():
    data = {
        "provider": "gemini",
        "input_path": "input",
        "messages": [],
        "pending_summary": [],
    }

    restored = restore_conversation_session(data, documents=[])

    assert restored.prompt_template is None


@pytest.mark.parametrize(
    "invalid",
    ["", " analisar.md", "folder/analisar.md", r"folder\analisar.md", "prompt.json"],
)
def test_session_rejects_non_filename_prompt_template(invalid):
    with pytest.raises(ValueError, match="must be a .md or .txt filename"):
        ConversationSession(
            provider="openai",
            documents=[],
            prompt_template=invalid,
        )


def test_list_sessions_returns_empty_for_missing_directory(tmp_path):
    assert list_sessions(tmp_path / "missing") == []


def test_list_sessions_returns_sorted_json_names_only(tmp_path):
    (tmp_path / "zeta.json").write_text("{}", encoding="utf-8")
    (tmp_path / "alpha.json").write_text("{}", encoding="utf-8")
    (tmp_path / "ignored.txt").write_text("ignored", encoding="utf-8")
    (tmp_path / "folder.json").mkdir()

    assert list_sessions(tmp_path) == ["alpha", "zeta"]


def test_load_session_data_rejects_missing_session(tmp_path):
    with pytest.raises(FileNotFoundError, match="Session not found: missing"):
        load_session_data("missing", sessions_dir=tmp_path)


def test_delete_session_reports_existing_and_missing_session(tmp_path):
    session_path = tmp_path / "temporary.json"
    session_path.write_text("{}", encoding="utf-8")

    assert delete_session("temporary", sessions_dir=tmp_path) is True
    assert session_path.exists() is False
    assert delete_session("temporary", sessions_dir=tmp_path) is False
