import builtins
import importlib.util
from pathlib import Path

import ai_engine
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
