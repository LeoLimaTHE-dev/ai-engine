import importlib.util
from pathlib import Path

import pytest

from ai_engine import ProviderError
from ai_engine.results import OutputRequest, StructuredResult
from ai_engine.structured_errors import (
    OutputExecutionError,
    OutputValidationError,
    StructuredParseError,
)


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "application" / "ia_interativa.py"
SPEC = importlib.util.spec_from_file_location(
    "ia_interativa_structured_outputs_test",
    SCRIPT_PATH,
)
assert SPEC is not None
assert SPEC.loader is not None
ia_interativa = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(ia_interativa)


class FakeSession:
    def __init__(self):
        self.provider = "openai"
        self.documents = []
        self.messages = ["existing"]
        self.pending_summary = ["pending"]
        self.summary = "summary"
        self.should_update_summary = False

    def build_conversation_prompt(self, current_user_message):
        return current_user_message

    def clear_history(self):
        self.messages.clear()
        self.pending_summary.clear()
        self.summary = ""


def configure_run_chat(monkeypatch, answers):
    prompts = []
    answers = iter(answers)

    def fake_input(prompt):
        prompts.append(prompt)
        return next(answers)

    monkeypatch.setattr("builtins.input", fake_input)
    monkeypatch.setattr(ia_interativa, "save_session", lambda **kwargs: None)
    monkeypatch.setattr(ia_interativa, "analyze_documents", lambda **kwargs: object())
    monkeypatch.setattr(
        ia_interativa,
        "confirm_preflight_interactively",
        lambda report: True,
    )
    monkeypatch.setattr(ia_interativa, "get_usage_totals", lambda: {})
    monkeypatch.setattr(ia_interativa, "print_operation_usage", lambda **kwargs: None)
    return prompts


def run_loop(module_session):
    ia_interativa.run_chat(
        session_name="Offline",
        session=module_session,
        input_path=Path("input"),
    )


@pytest.mark.parametrize(
    "choice",
    ["", "n", "talvez", " N ", "não"],
)
def test_ask_expect_outputs_defaults_to_false(choice, monkeypatch):
    monkeypatch.setattr("builtins.input", lambda prompt: choice)

    assert ia_interativa.ask_expect_outputs() is False


@pytest.mark.parametrize(
    "choice",
    ["s", "sim", "y", "yes", " S ", "SIM", " Yes "],
)
def test_ask_expect_outputs_accepts_explicit_affirmative_values(choice, monkeypatch):
    monkeypatch.setattr("builtins.input", lambda prompt: choice)

    assert ia_interativa.ask_expect_outputs() is True


@pytest.mark.parametrize(
    ("message", "choice", "expected"),
    [
        ("mensagem normal", "n", False),
        ("mensagem normal", "sim", True),
        ("gere um DOCX", "n", False),
        ("Olá", "sim", True),
    ],
)
def test_normal_turn_forwards_only_explicit_expect_outputs_choice(
    message,
    choice,
    expected,
    monkeypatch,
):
    session = FakeSession()
    prompts = configure_run_chat(monkeypatch, [message, choice, "sair"])
    calls = []

    def fake_chat(**kwargs):
        calls.append(kwargs)
        return StructuredResult(message="Resposta textual")

    monkeypatch.setattr(ia_interativa, "chat", fake_chat)

    run_loop(session)

    assert calls[0]["expect_outputs"] is expected
    assert sum("Espera arquivos" in prompt for prompt in prompts) == 1


@pytest.mark.parametrize("command", ["sair", "limpar", "uso", "provider", "salvar"])
def test_internal_commands_do_not_ask_if_outputs_are_expected(
    command,
    monkeypatch,
):
    session = FakeSession()
    answers = [command] if command == "sair" else [command, "sair"]
    prompts = configure_run_chat(monkeypatch, answers)
    monkeypatch.setattr(ia_interativa, "format_usage_summary", lambda usage: "usage")
    monkeypatch.setattr(ia_interativa, "change_session_provider", lambda session: False)

    run_loop(session)

    assert not any("Espera arquivos" in prompt for prompt in prompts)


def test_structured_parse_error_is_friendly_and_does_not_execute_actions(
    monkeypatch,
    capsys,
):
    session = FakeSession()
    original_state = (list(session.messages), list(session.pending_summary), session.summary)
    configure_run_chat(monkeypatch, ["pedido", "sim", "sair"])

    def fail_chat(**kwargs):
        raise StructuredParseError(
            "invalid response",
            details={"raw_preview": "must not be printed"},
        )

    monkeypatch.setattr(ia_interativa, "chat", fail_chat)
    monkeypatch.setattr(
        ia_interativa,
        "execute_structured_result",
        lambda **kwargs: pytest.fail("actions must not run after a parse error"),
    )

    run_loop(session)
    output = capsys.readouterr().out

    assert "não veio no formato estruturado esperado" in output
    assert "Nenhum arquivo foi criado" in output
    assert "must not be printed" not in output
    assert "Traceback" not in output
    assert (session.messages, session.pending_summary, session.summary) == original_state


def test_output_validation_error_shows_field_and_does_not_execute_actions(
    monkeypatch,
    capsys,
):
    session = FakeSession()
    configure_run_chat(monkeypatch, ["pedido", "sim", "sair"])

    def fail_chat(**kwargs):
        raise OutputValidationError(
            "unsupported format",
            field_path="outputs[0].format",
            details={"model-data": "must not be printed"},
        )

    monkeypatch.setattr(ia_interativa, "chat", fail_chat)
    monkeypatch.setattr(
        ia_interativa,
        "execute_structured_result",
        lambda **kwargs: pytest.fail("actions must not run after validation failure"),
    )

    run_loop(session)
    output = capsys.readouterr().out

    assert "contém dados inválidos" in output
    assert "Campo problemático: outputs[0].format" in output
    assert "Detalhe: unsupported format" in output
    assert "must not be printed" not in output


def test_output_execution_error_reports_possible_partial_write(
    monkeypatch,
    capsys,
):
    session = FakeSession()
    configure_run_chat(monkeypatch, ["pedido", "sim", "sair"])
    result = StructuredResult(
        message="Plano criado",
        outputs=[OutputRequest(format="txt", filename="one.txt", content="body")],
    )
    monkeypatch.setattr(ia_interativa, "chat", lambda **kwargs: result)

    def fail_execution(**kwargs):
        raise OutputExecutionError(
            "disk failure",
            field_path="outputs[1]",
            details={"local": "must not be printed"},
        )

    monkeypatch.setattr(ia_interativa, "execute_structured_result", fail_execution)

    run_loop(session)
    output = capsys.readouterr().out

    assert "plano era válido" in output
    assert "Output que falhou: outputs[1]" in output
    assert "Detalhe: disk failure" in output
    assert "Nenhum arquivo foi criado" not in output
    assert "must not be printed" not in output


def test_empty_outputs_are_valid_and_do_not_execute_actions(monkeypatch, capsys):
    session = FakeSession()
    configure_run_chat(monkeypatch, ["pedido", "sim", "sair"])
    monkeypatch.setattr(
        ia_interativa,
        "chat",
        lambda **kwargs: StructuredResult(
            message="Não foi possível gerar.",
            outputs=[],
        ),
    )
    monkeypatch.setattr(
        ia_interativa,
        "execute_structured_result",
        lambda **kwargs: pytest.fail("empty outputs must not execute actions"),
    )

    run_loop(session)

    assert "Não foi possível gerar." in capsys.readouterr().out


def test_empty_message_with_outputs_still_executes_and_prints_paths(
    monkeypatch,
    capsys,
    tmp_path,
):
    session = FakeSession()
    configure_run_chat(monkeypatch, ["pedido", "sim", "sair"])
    result = StructuredResult(
        message="",
        outputs=[OutputRequest(format="txt", filename="one.txt", content="body")],
    )
    created = tmp_path / "one.txt"
    monkeypatch.setattr(ia_interativa, "chat", lambda **kwargs: result)
    calls = []

    def fake_execute(**kwargs):
        calls.append(kwargs)
        return [created]

    monkeypatch.setattr(ia_interativa, "execute_structured_result", fake_execute)

    run_loop(session)
    output = capsys.readouterr().out

    assert calls == [{"result": result, "output_dir": ia_interativa.DEFAULT_OUTPUT_DIR}]
    assert str(created) in output


def test_provider_error_keeps_existing_provider_handling(monkeypatch, capsys):
    session = FakeSession()
    configure_run_chat(monkeypatch, ["pedido", "n", "sair"])

    def fail_chat(**kwargs):
        raise ProviderError(
            provider="openai",
            message="provider failure",
            retryable=False,
        )

    monkeypatch.setattr(ia_interativa, "chat", fail_chat)

    run_loop(session)
    output = capsys.readouterr().out

    assert "ERRO NA CHAMADA DA API" in output
    assert "Provider: openai" in output
