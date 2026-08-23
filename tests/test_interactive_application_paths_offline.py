import ast
import builtins
import importlib.util
from pathlib import Path

import ai_engine
import pytest
from ai_engine import PreflightReport, format_preflight
from ai_engine.limits import confirm_preflight as legacy_confirm_preflight
from ai_engine.session import ConversationSession


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "application" / "ia_interativa.py"


def fail_if_called(*args, **kwargs):
    raise AssertionError("Importing ia_interativa.py must not start the application")


def load_interface(monkeypatch, module_name, root=None):
    if root is None:
        monkeypatch.delenv("IA_ROOT", raising=False)
    else:
        monkeypatch.setenv("IA_ROOT", str(root))

    monkeypatch.setattr(builtins, "input", fail_if_called)
    monkeypatch.setattr(ai_engine, "chat", fail_if_called)

    spec = importlib.util.spec_from_file_location(module_name, SCRIPT_PATH)
    assert spec is not None
    assert spec.loader is not None

    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    return module


def test_importing_interface_does_not_start_application(monkeypatch):
    module = load_interface(
        monkeypatch,
        "ia_interativa_import_guard_test",
    )

    assert callable(module.main)
    assert callable(module.run_chat)


def test_interface_preserves_current_defaults_without_ia_root(monkeypatch):
    module = load_interface(
        monkeypatch,
        "ia_interativa_current_defaults_test",
    )

    assert module.DEFAULT_INPUT == Path(r"C:\IA\2_Entrada\batch_teste")
    assert module.DEFAULT_OUTPUT_DIR == Path(r"C:\IA\3_Saída")
    assert module.PATHS.sessions_dir == Path(r"C:\IA\6_Dados\sessions")


def test_interface_derives_defaults_and_session_message_from_ia_root(
    monkeypatch,
    tmp_path,
    capsys,
):
    module = load_interface(
        monkeypatch,
        "ia_interativa_custom_root_test",
        root=tmp_path,
    )

    assert module.DEFAULT_INPUT == tmp_path / "2_Entrada" / "batch_teste"
    assert module.DEFAULT_OUTPUT_DIR == tmp_path / "3_Saída"
    assert module.PATHS.sessions_dir == tmp_path / "6_Dados" / "sessions"

    monkeypatch.setattr(builtins, "input", lambda prompt: "sair")
    monkeypatch.setattr(module, "save_session", lambda **kwargs: None)
    session = ConversationSession(provider="gemini", documents=[])

    module.run_chat(
        session_name="Offline",
        session=session,
        input_path=module.DEFAULT_INPUT,
    )

    assert str(module.PATHS.sessions_dir) in capsys.readouterr().out


def test_choose_input_still_allows_user_override(monkeypatch, tmp_path):
    module = load_interface(
        monkeypatch,
        "ia_interativa_input_override_test",
        root=tmp_path,
    )
    chosen_path = tmp_path / "custom input"
    monkeypatch.setattr(builtins, "input", lambda prompt: f'"{chosen_path}"')

    assert module.choose_input() == chosen_path


def test_choose_input_explains_documentless_default(monkeypatch, tmp_path):
    module = load_interface(
        monkeypatch,
        "ia_interativa_documentless_prompt_test",
        root=tmp_path,
    )
    prompts = []
    monkeypatch.setattr(
        builtins,
        "input",
        lambda prompt: prompts.append(prompt) or "",
    )

    assert module.choose_input() == module.DEFAULT_INPUT
    assert "sem documentos se vazio" in prompts[0]


def test_new_session_accepts_empty_default_directory_and_saves(
    monkeypatch,
    tmp_path,
    capsys,
):
    module = load_interface(
        monkeypatch,
        "ia_interativa_documentless_creation_test",
        root=tmp_path,
    )
    module.DEFAULT_INPUT.mkdir(parents=True)
    answers = iter(["Text only session", ""])
    saved = []
    monkeypatch.setattr(builtins, "input", lambda prompt: next(answers))
    monkeypatch.setattr(module, "choose_provider", lambda: "openai")
    monkeypatch.setattr(module, "choose_prompt_template", lambda: None)
    monkeypatch.setattr(
        module,
        "save_session",
        lambda **kwargs: saved.append(kwargs) or tmp_path / "saved.json",
    )

    name, session, input_path = module.create_new_session()

    assert name == "Text only session"
    assert input_path == module.DEFAULT_INPUT
    assert session.documents == []
    assert saved[0]["session"] is session
    assert saved[0]["input_path"] == module.DEFAULT_INPUT
    output = capsys.readouterr().out
    assert "Nenhum documento suportado encontrado." in output
    assert "A sessão continuará somente com o chat." in output


def test_restore_session_accepts_existing_empty_input_directory(
    monkeypatch,
    tmp_path,
):
    module = load_interface(
        monkeypatch,
        "ia_interativa_documentless_restore_test",
        root=tmp_path,
    )
    input_path = tmp_path / "empty-input"
    input_path.mkdir()
    saved = []
    monkeypatch.setattr(module, "select_existing_session_name", lambda: "Text only")
    monkeypatch.setattr(
        module,
        "load_session_data",
        lambda name: {
            "provider": "openai",
            "input_path": str(input_path),
            "prompt_template": None,
            "messages": [],
            "pending_summary": [],
        },
    )
    monkeypatch.setattr(
        module,
        "save_session",
        lambda **kwargs: saved.append(kwargs) or tmp_path / "saved.json",
    )

    name, session, restored_path = module.restore_saved_session()

    assert name == "Text only"
    assert restored_path == input_path
    assert session.documents == []
    assert saved[0]["session"] is session


def test_interface_uses_public_api_except_internal_structured_error_contract():
    tree = ast.parse(SCRIPT_PATH.read_text(encoding="utf-8"))
    engine_imports = [
        node
        for node in ast.walk(tree)
        if (
            isinstance(node, (ast.Import, ast.ImportFrom))
            and (
                (isinstance(node, ast.ImportFrom) and node.module == "ai_engine")
                or (
                    isinstance(node, ast.Import)
                    and any(alias.name == "ai_engine" for alias in node.names)
                )
            )
        )
    ]
    internal_imports = [
        node
        for node in ast.walk(tree)
        if (
            isinstance(node, ast.ImportFrom)
            and node.module is not None
            and node.module.startswith("ai_engine.")
        )
        or (
            isinstance(node, ast.Import)
            and any(alias.name.startswith("ai_engine.") for alias in node.names)
        )
    ]

    assert len(engine_imports) == 1
    assert isinstance(engine_imports[0], ast.ImportFrom)
    assert [node.module for node in internal_imports] == [
        "ai_engine.structured_errors"
    ]


def make_preflight_report(errors=None):
    return PreflightReport(
        file_count=1,
        text_characters=4,
        estimated_text_tokens=1,
        image_count=0,
        image_bytes=0,
        errors=errors or [],
    )


def assert_confirmation_matches_legacy(
    module,
    report,
    choice,
    expected,
    monkeypatch,
    capsys,
):
    monkeypatch.setattr(builtins, "input", lambda prompt: choice)

    legacy_result = legacy_confirm_preflight(report)
    legacy_output = capsys.readouterr().out

    local_result = module.confirm_preflight_interactively(report)
    local_output = capsys.readouterr().out

    assert local_result is expected
    assert local_result is legacy_result
    assert local_output == legacy_output
    assert format_preflight(report) in local_output


@pytest.mark.parametrize(
    ("choice", "expected"),
    [
        ("s", True),
        ("sim", True),
        ("y", True),
        ("yes", True),
        ("", False),
        ("n", False),
    ],
)
def test_local_normal_confirmation_matches_legacy(
    choice,
    expected,
    monkeypatch,
    capsys,
):
    module = load_interface(
        monkeypatch,
        "ia_interativa_normal_confirmation_test",
    )

    assert_confirmation_matches_legacy(
        module=module,
        report=make_preflight_report(),
        choice=choice,
        expected=expected,
        monkeypatch=monkeypatch,
        capsys=capsys,
    )


@pytest.mark.parametrize(
    ("choice", "expected"),
    [
        ("CONFIRMAR", True),
        (" CONFIRMAR ", True),
        ("confirmar", False),
        ("s", False),
        ("sim", False),
        ("y", False),
        ("yes", False),
    ],
)
def test_local_blocked_confirmation_matches_legacy(
    choice,
    expected,
    monkeypatch,
    capsys,
):
    module = load_interface(
        monkeypatch,
        "ia_interativa_blocked_confirmation_test",
    )

    assert_confirmation_matches_legacy(
        module=module,
        report=make_preflight_report(errors=["Maximum exceeded"]),
        choice=choice,
        expected=expected,
        monkeypatch=monkeypatch,
        capsys=capsys,
    )
