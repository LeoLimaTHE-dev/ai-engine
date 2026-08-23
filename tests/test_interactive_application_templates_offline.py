import importlib.util
from pathlib import Path

import pytest

from ai_engine import PromptTemplate


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "application" / "ia_interativa.py"
SPEC = importlib.util.spec_from_file_location(
    "ia_interativa_templates_test",
    SCRIPT_PATH,
)
assert SPEC is not None
assert SPEC.loader is not None
ia_interativa = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(ia_interativa)


TEMPLATES = [
    PromptTemplate(
        filename="analisar_documentos.md",
        name="Analisar documentos",
        description="Descrição carregada da metadata.",
    ),
    PromptTemplate(
        filename="resumir.md",
        name="Resumir",
        description="Produz uma síntese objetiva.",
    ),
]


@pytest.mark.parametrize("choice", ["", "0"])
def test_choose_prompt_template_defaults_to_none(choice, monkeypatch, capsys):
    monkeypatch.setattr(ia_interativa, "discover_prompt_templates", lambda: TEMPLATES)
    monkeypatch.setattr("builtins.input", lambda prompt: choice)

    assert ia_interativa.choose_prompt_template() is None

    output = capsys.readouterr().out
    assert "[0] Nenhum — conversa normal" in output
    assert "Template selecionado: Nenhum" in output


def test_choose_prompt_template_returns_discovered_filename_and_description(
    monkeypatch,
    capsys,
):
    monkeypatch.setattr(ia_interativa, "discover_prompt_templates", lambda: TEMPLATES)
    monkeypatch.setattr("builtins.input", lambda prompt: "1")

    selected = ia_interativa.choose_prompt_template()

    assert selected is TEMPLATES[0]
    assert selected.filename == "analisar_documentos.md"
    output = capsys.readouterr().out
    assert "[1] Analisar documentos" in output
    assert "    Descrição carregada da metadata." in output
    assert "Template selecionado: Analisar documentos" in output


def test_invalid_template_choice_repeats_until_valid(monkeypatch, capsys):
    answers = iter(["invalid", "3", "2"])
    monkeypatch.setattr(ia_interativa, "discover_prompt_templates", lambda: TEMPLATES)
    monkeypatch.setattr("builtins.input", lambda prompt: next(answers))

    selected = ia_interativa.choose_prompt_template()

    assert selected is TEMPLATES[1]
    assert capsys.readouterr().out.count("Escolha inválida") == 2


def test_no_discoverable_templates_continues_with_none_without_asking(
    monkeypatch,
    capsys,
):
    monkeypatch.setattr(ia_interativa, "discover_prompt_templates", lambda: [])
    monkeypatch.setattr(
        "builtins.input",
        lambda prompt: pytest.fail("empty template list must not ask for a choice"),
    )

    assert ia_interativa.choose_prompt_template() is None
    assert "Template selecionado: Nenhum" in capsys.readouterr().out


def test_experimental_prompt_without_metadata_does_not_appear(
    monkeypatch,
    tmp_path,
    capsys,
):
    prompts_dir = tmp_path / "4_Prompts"
    prompts_dir.mkdir()
    (prompts_dir / "experimental.md").write_text(
        "Experimental instructions without menu metadata.",
        encoding="utf-8",
    )
    monkeypatch.setenv("IA_ROOT", str(tmp_path))
    monkeypatch.setattr(
        "builtins.input",
        lambda prompt: pytest.fail("experimental prompt must not create a choice"),
    )

    assert ia_interativa.choose_prompt_template() is None
    assert "experimental" not in capsys.readouterr().out.lower()


@pytest.mark.parametrize(
    ("choice", "expected_filename"),
    [("", None), ("1", "analisar_documentos.md")],
)
def test_new_session_persists_selected_template(
    choice,
    expected_filename,
    monkeypatch,
    tmp_path,
):
    answers = iter(["Session name", choice])
    saved_sessions = []
    input_path = tmp_path / "input"

    monkeypatch.setattr("builtins.input", lambda prompt: next(answers))
    monkeypatch.setattr(ia_interativa, "choose_provider", lambda: "openai")
    monkeypatch.setattr(ia_interativa, "choose_input", lambda: input_path)
    monkeypatch.setattr(
        ia_interativa,
        "load_documents",
        lambda path, **kwargs: [],
    )
    monkeypatch.setattr(ia_interativa, "discover_prompt_templates", lambda: TEMPLATES)
    monkeypatch.setattr(
        ia_interativa,
        "save_session",
        lambda **kwargs: saved_sessions.append(kwargs) or tmp_path / "session.json",
    )

    _, session, _ = ia_interativa.create_new_session()

    assert session.prompt_template == expected_filename
    assert saved_sessions[0]["session"] is session
    assert saved_sessions[0]["session"].prompt_template == expected_filename


def _configure_restore(monkeypatch, tmp_path, prompt_template, templates):
    input_path = tmp_path / "input"
    input_path.mkdir()
    saved_sessions = []
    data = {
        "provider": "openai",
        "input_path": str(input_path),
        "prompt_template": prompt_template,
        "messages": [],
        "pending_summary": [],
    }

    monkeypatch.setattr(
        "builtins.input",
        lambda prompt: pytest.fail("restoration must not ask for a template"),
    )
    monkeypatch.setattr(
        ia_interativa,
        "select_existing_session_name",
        lambda: "Existing",
    )
    monkeypatch.setattr(ia_interativa, "load_session_data", lambda name: data)
    monkeypatch.setattr(
        ia_interativa,
        "load_documents",
        lambda path, **kwargs: [],
    )
    monkeypatch.setattr(
        ia_interativa,
        "discover_prompt_templates",
        lambda: templates,
    )
    monkeypatch.setattr(
        ia_interativa,
        "save_session",
        lambda **kwargs: saved_sessions.append(kwargs) or tmp_path / "session.json",
    )
    monkeypatch.setattr(
        ia_interativa,
        "chat",
        lambda **kwargs: pytest.fail("template restoration must not call a provider"),
    )
    return saved_sessions


def test_restore_preserves_valid_template_without_asking(
    monkeypatch,
    tmp_path,
    capsys,
):
    saved_sessions = _configure_restore(
        monkeypatch,
        tmp_path,
        prompt_template="analisar_documentos.md",
        templates=TEMPLATES,
    )

    _, session, _ = ia_interativa.restore_saved_session()

    assert session.prompt_template == "analisar_documentos.md"
    assert saved_sessions[0]["session"].prompt_template == "analisar_documentos.md"
    assert "Template da sessão: Analisar documentos" in capsys.readouterr().out


def test_restore_missing_template_warns_falls_back_and_saves(
    monkeypatch,
    tmp_path,
    capsys,
):
    saved_sessions = _configure_restore(
        monkeypatch,
        tmp_path,
        prompt_template="removed.md",
        templates=TEMPLATES,
    )

    _, session, _ = ia_interativa.restore_saved_session()

    assert session.prompt_template is None
    assert saved_sessions[0]["session"].prompt_template is None
    output = capsys.readouterr().out
    assert 'Aviso: o template "removed.md" não foi encontrado.' in output
    assert "A sessão continuará sem template." in output
