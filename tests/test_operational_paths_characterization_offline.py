from pathlib import Path

from ai_engine.prompts import DEFAULT_PROMPTS_DIR, load_prompt
from ai_engine.session import ConversationSession
from ai_engine.sessions import (
    DEFAULT_SESSIONS_DIR,
    delete_session,
    get_session_path,
    list_sessions,
    load_session_data,
    save_session,
)
from ai_engine.usage import (
    DEFAULT_USAGE_DIR,
    DEFAULT_USAGE_FILE,
    UsageRecord,
    get_usage_totals,
    log_usage,
)


def test_current_operational_path_defaults_are_preserved():
    assert DEFAULT_PROMPTS_DIR == Path(r"C:\IA\4_Prompts")
    assert DEFAULT_SESSIONS_DIR == Path(r"C:\IA\6_Dados\sessions")
    assert DEFAULT_USAGE_DIR == Path(r"C:\IA\6_Dados\usage")
    assert DEFAULT_USAGE_FILE == DEFAULT_USAGE_DIR / "api_usage.csv"


def test_explicit_prompts_directory_overrides_the_default(tmp_path):
    prompts_dir = tmp_path / "prompts"
    prompts_dir.mkdir()
    (prompts_dir / "characterization.md").write_text(
        "Explicit prompt directory",
        encoding="utf-8",
    )

    assert (
        load_prompt("characterization", prompts_dir=prompts_dir)
        == "Explicit prompt directory"
    )


def test_explicit_sessions_directory_contains_all_session_operations(tmp_path):
    sessions_dir = tmp_path / "sessions"
    input_path = Path(r"D:\External Inputs\documents")
    session = ConversationSession(provider="gemini", documents=[])

    expected_path = get_session_path(
        "Characterization Session",
        sessions_dir=sessions_dir,
    )
    saved_path = save_session(
        name="Characterization Session",
        session=session,
        input_path=input_path,
        sessions_dir=sessions_dir,
    )
    data = load_session_data(
        "Characterization Session",
        sessions_dir=sessions_dir,
    )

    assert expected_path == sessions_dir / "Characterization_Session.json"
    assert saved_path == expected_path
    assert saved_path.is_relative_to(tmp_path)
    assert data["input_path"] == str(input_path)
    assert list_sessions(sessions_dir=sessions_dir) == ["Characterization_Session"]
    assert delete_session(
        "Characterization Session",
        sessions_dir=sessions_dir,
    )
    assert expected_path.exists() is False


def test_explicit_usage_file_contains_all_usage_operations(tmp_path):
    usage_file = tmp_path / "usage" / "characterization.csv"
    record = UsageRecord(
        provider="offline",
        model="characterization",
        input_tokens=2,
        output_tokens=3,
        total_tokens=5,
        timestamp="2026-08-22T00:00:00",
    )

    saved_path = log_usage(record, usage_file=usage_file)

    assert saved_path == usage_file
    assert saved_path.is_relative_to(tmp_path)
    assert get_usage_totals(usage_file=usage_file) == {
        "requests": 1,
        "input_tokens": 2,
        "output_tokens": 3,
        "thought_tokens": 0,
        "cached_tokens": 0,
        "total_tokens": 5,
    }
