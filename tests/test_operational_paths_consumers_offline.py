from pathlib import Path

from ai_engine.prompts import load_prompt
from ai_engine.session import ConversationSession
from ai_engine.sessions import (
    get_session_path,
    list_sessions,
    load_session_data,
    save_session,
)
from ai_engine.usage import (
    UsageRecord,
    get_usage_totals,
    log_usage,
)


def test_load_prompt_uses_environment_prompts_directory(monkeypatch, tmp_path):
    prompts_dir = tmp_path / "4_Prompts"
    prompts_dir.mkdir()
    (prompts_dir / "dynamic.md").write_text("Dynamic prompt", encoding="utf-8")
    monkeypatch.setenv("IA_ROOT", str(tmp_path))

    assert load_prompt("dynamic") == "Dynamic prompt"


def test_explicit_prompts_directory_precedes_environment(monkeypatch, tmp_path):
    environment_root = tmp_path / "environment"
    explicit_dir = tmp_path / "explicit"
    explicit_dir.mkdir()
    (explicit_dir / "chosen.md").write_text("Explicit prompt", encoding="utf-8")
    monkeypatch.setenv("IA_ROOT", str(environment_root))

    assert load_prompt("chosen", prompts_dir=explicit_dir) == "Explicit prompt"


def test_session_round_trip_uses_environment_sessions_directory(
    monkeypatch,
    tmp_path,
):
    monkeypatch.setenv("IA_ROOT", str(tmp_path))
    input_path = Path(r"D:\Preserved Input\documents")
    session = ConversationSession(provider="gemini", documents=[])

    saved_path = save_session(
        name="Dynamic Session",
        session=session,
        input_path=input_path,
    )
    data = load_session_data("Dynamic Session")

    expected_dir = tmp_path / "6_Dados" / "sessions"
    assert saved_path == expected_dir / "Dynamic_Session.json"
    assert list_sessions() == ["Dynamic_Session"]
    assert data["input_path"] == str(input_path)


def test_explicit_sessions_directory_precedes_environment(monkeypatch, tmp_path):
    environment_root = tmp_path / "environment"
    explicit_dir = tmp_path / "explicit-sessions"
    monkeypatch.setenv("IA_ROOT", str(environment_root))

    path = get_session_path("Explicit Session", sessions_dir=explicit_dir)

    assert path == explicit_dir / "Explicit_Session.json"


def test_usage_uses_environment_usage_file(monkeypatch, tmp_path):
    monkeypatch.setenv("IA_ROOT", str(tmp_path))
    record = UsageRecord(
        provider="offline",
        model="dynamic-default",
        total_tokens=7,
        timestamp="2026-08-22T00:00:00",
    )

    saved_path = log_usage(record)

    expected_file = tmp_path / "6_Dados" / "usage" / "api_usage.csv"
    assert saved_path == expected_file
    assert get_usage_totals() == {
        "requests": 1,
        "input_tokens": 0,
        "output_tokens": 0,
        "thought_tokens": 0,
        "cached_tokens": 0,
        "total_tokens": 7,
    }


def test_explicit_usage_file_precedes_environment(monkeypatch, tmp_path):
    environment_root = tmp_path / "environment"
    explicit_file = tmp_path / "explicit" / "usage.csv"
    monkeypatch.setenv("IA_ROOT", str(environment_root))
    record = UsageRecord(
        provider="offline",
        model="explicit",
        timestamp="2026-08-22T00:00:00",
    )

    saved_path = log_usage(record, usage_file=explicit_file)

    assert saved_path == explicit_file
    assert get_usage_totals(usage_file=explicit_file)["requests"] == 1
    assert (environment_root / "6_Dados").exists() is False


def test_changing_environment_root_changes_defaults_between_calls(
    monkeypatch,
    tmp_path,
):
    first_root = tmp_path / "first"
    second_root = tmp_path / "second"

    monkeypatch.setenv("IA_ROOT", str(first_root))
    first_path = get_session_path("Same Session")

    monkeypatch.setenv("IA_ROOT", str(second_root))
    second_path = get_session_path("Same Session")

    assert first_path == first_root / "6_Dados" / "sessions" / "Same_Session.json"
    assert second_path == (
        second_root / "6_Dados" / "sessions" / "Same_Session.json"
    )
