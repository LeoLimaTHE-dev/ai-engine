import importlib.util
import sys
from dataclasses import FrozenInstanceError
from pathlib import Path

import pytest

from ai_engine.paths import DEFAULT_IA_ROOT, get_paths


def test_get_paths_falls_back_to_current_root_without_environment(monkeypatch):
    monkeypatch.delenv("IA_ROOT", raising=False)

    assert get_paths().root == Path(r"C:\IA")
    assert DEFAULT_IA_ROOT == Path(r"C:\IA")


def test_get_paths_derives_all_nine_current_paths(monkeypatch):
    monkeypatch.delenv("IA_ROOT", raising=False)

    paths = get_paths()

    assert paths.root == Path(r"C:\IA")
    assert paths.input_dir == paths.root / "2_Entrada"
    assert paths.output_dir == paths.root / "3_Saída"
    assert paths.prompts_dir == paths.root / "4_Prompts"
    assert paths.models_dir == paths.root / "5_Modelos"
    assert paths.data_dir == paths.root / "6_Dados"
    assert paths.sessions_dir == paths.data_dir / "sessions"
    assert paths.usage_dir == paths.data_dir / "usage"
    assert paths.temp_dir == paths.root / "7_Temporario"


def test_get_paths_uses_environment_root(monkeypatch, tmp_path):
    monkeypatch.setenv("IA_ROOT", str(tmp_path))

    paths = get_paths()

    assert paths.root == tmp_path
    assert paths.input_dir == tmp_path / "2_Entrada"
    assert paths.output_dir == tmp_path / "3_Saída"
    assert paths.prompts_dir == tmp_path / "4_Prompts"
    assert paths.models_dir == tmp_path / "5_Modelos"
    assert paths.data_dir == tmp_path / "6_Dados"
    assert paths.sessions_dir == tmp_path / "6_Dados" / "sessions"
    assert paths.usage_dir == tmp_path / "6_Dados" / "usage"
    assert paths.temp_dir == tmp_path / "7_Temporario"


def test_explicit_root_takes_priority_over_environment(monkeypatch, tmp_path):
    environment_root = tmp_path / "environment"
    explicit_root = tmp_path / "explicit"
    monkeypatch.setenv("IA_ROOT", str(environment_root))

    assert get_paths(root=explicit_root).root == explicit_root


def test_operational_paths_are_immutable(tmp_path):
    paths = get_paths(root=tmp_path)

    with pytest.raises(FrozenInstanceError):
        paths.root = tmp_path / "changed"


def test_get_paths_does_not_create_directories(tmp_path):
    missing_root = tmp_path / "missing root"

    paths = get_paths(root=missing_root)

    assert paths.root == missing_root
    assert missing_root.exists() is False
    assert paths.input_dir.exists() is False
    assert paths.data_dir.exists() is False


@pytest.mark.parametrize("value", ["", "   "])
def test_empty_environment_root_is_rejected(monkeypatch, value):
    monkeypatch.setenv("IA_ROOT", value)

    with pytest.raises(ValueError, match="cannot be empty"):
        get_paths()


@pytest.mark.parametrize("value", ["", "   "])
def test_empty_explicit_root_is_rejected(value):
    with pytest.raises(ValueError, match="cannot be empty"):
        get_paths(root=value)


def test_relative_explicit_root_is_rejected():
    with pytest.raises(ValueError, match="must be an absolute path"):
        get_paths(root=Path("relative-root"))


def test_relative_environment_root_is_rejected(monkeypatch):
    monkeypatch.setenv("IA_ROOT", "relative-root")

    with pytest.raises(ValueError, match="must be an absolute path"):
        get_paths()


def test_absolute_root_with_spaces_and_accents_is_preserved(tmp_path):
    root = tmp_path / "Ambiente com espaços" / "Saída temporária"

    paths = get_paths(root=root)

    assert paths.root == root
    assert paths.output_dir == root / "3_Saída"
    assert paths.temp_dir == root / "7_Temporario"


def test_get_paths_does_not_change_sys_path(monkeypatch, tmp_path):
    original_sys_path = sys.path.copy()
    monkeypatch.setenv("IA_ROOT", str(tmp_path))

    get_paths()

    assert sys.path == original_sys_path


def test_changing_ia_root_does_not_change_ai_engine_resolution(
    monkeypatch,
    tmp_path,
):
    before = importlib.util.find_spec("ai_engine")
    assert before is not None

    monkeypatch.setenv("IA_ROOT", str(tmp_path))
    get_paths()

    after = importlib.util.find_spec("ai_engine")
    assert after is not None
    assert after.origin == before.origin
