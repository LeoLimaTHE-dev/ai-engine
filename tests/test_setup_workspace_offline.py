import os
import shutil
import subprocess
from pathlib import Path

import pytest


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SETUP_SCRIPT = PROJECT_ROOT / "scripts" / "setup_workspace.ps1"
ENVIRONMENT_EXAMPLE = PROJECT_ROOT / ".env.example"
WORKSPACE_ASSETS = PROJECT_ROOT / "workspace_assets"
OFFICIAL_PROMPTS = (
    "resumir.md",
    "analisar_documentos.md",
    "comparar_arquivos.md",
    "relatorio_multimodal_com_imagens.md",
)
OFFICIAL_MANUAL = "Guia_Ambiente_IA_Multi_Provider_v1.1.0.docx"


def _powershell_executable() -> str:
    executable = shutil.which("pwsh") or shutil.which("powershell")
    if executable is None:
        pytest.skip("PowerShell is required to test setup_workspace.ps1")
    return executable


@pytest.fixture
def portable_repo(tmp_path: Path) -> tuple[Path, Path]:
    root = tmp_path / "Portable Workspace"
    repo = root / "api"
    scripts = repo / "scripts"
    assets = repo / "workspace_assets"

    scripts.mkdir(parents=True)
    shutil.copy2(SETUP_SCRIPT, scripts / SETUP_SCRIPT.name)
    shutil.copytree(WORKSPACE_ASSETS, assets)
    shutil.copy2(ENVIRONMENT_EXAMPLE, repo / ENVIRONMENT_EXAMPLE.name)

    return root, repo


def _run_setup(
    root: Path,
    repo: Path,
    *arguments: str,
    environment: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    command = [
        _powershell_executable(),
        "-NoProfile",
        "-NonInteractive",
        "-ExecutionPolicy",
        "Bypass",
        "-File",
        str(repo / "scripts" / "setup_workspace.ps1"),
        "-Root",
        str(root),
        *arguments,
    ]
    return subprocess.run(
        command,
        cwd=repo,
        env=environment,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
        timeout=30,
    )


def _assert_success(completed: subprocess.CompletedProcess[str]) -> None:
    assert completed.returncode == 0, completed.stdout + completed.stderr


def test_setup_creates_workspace_tree_prompts_launcher_and_environment(
    portable_repo: tuple[Path, Path],
) -> None:
    root, repo = portable_repo

    completed = _run_setup(root, repo, "-SkipSync")

    _assert_success(completed)
    for relative_directory in (
        "1_Projetos",
        "2_Entrada",
        "2_Entrada/batch_teste",
        "3_Saída",
        "4_Prompts",
        "5_Modelos",
        "6_Dados",
        "6_Dados/sessions",
        "6_Dados/usage",
        "7_Temporario",
    ):
        assert (root / relative_directory).is_dir()

    for filename in OFFICIAL_PROMPTS:
        assert (root / "4_Prompts" / filename).read_bytes() == (
            repo / "workspace_assets" / "prompts" / filename
        ).read_bytes()

    assert (root / OFFICIAL_MANUAL).read_bytes() == (
        repo / "workspace_assets" / OFFICIAL_MANUAL
    ).read_bytes()

    launcher = (root / "Iniciar IA.bat").read_text(encoding="utf-8")
    assert f'set "IA_ROOT={root}"' in launcher
    assert f'cd /d "{repo}"' in launcher
    assert "uv run python application\\ia_interativa.py" in launcher
    assert (repo / ".env").read_bytes() == (repo / ".env.example").read_bytes()
    assert "uv sync desabilitado" in completed.stdout


def test_prompt_conflict_is_preserved_without_force_and_replaced_with_force(
    portable_repo: tuple[Path, Path],
) -> None:
    root, repo = portable_repo
    prompt_dir = root / "4_Prompts"
    prompt_dir.mkdir(parents=True)
    destination = prompt_dir / OFFICIAL_PROMPTS[0]
    destination.write_text("customizado", encoding="utf-8")

    first = _run_setup(root, repo, "-SkipSync")

    _assert_success(first)
    assert destination.read_text(encoding="utf-8") == "customizado"
    assert "[CONFLITO]" in first.stdout

    second = _run_setup(root, repo, "-SkipSync", "-Force")

    _assert_success(second)
    assert destination.read_bytes() == (
        repo / "workspace_assets" / "prompts" / destination.name
    ).read_bytes()


def test_setup_never_removes_custom_prompt(
    portable_repo: tuple[Path, Path],
) -> None:
    root, repo = portable_repo
    custom = root / "4_Prompts" / "meu_prompt.txt"
    custom.parent.mkdir(parents=True)
    custom.write_text("conteudo do usuario", encoding="utf-8")

    completed = _run_setup(root, repo, "-SkipSync", "-Force")

    _assert_success(completed)
    assert custom.read_text(encoding="utf-8") == "conteudo do usuario"


def test_launcher_conflict_is_preserved_then_force_replaces_it(
    portable_repo: tuple[Path, Path],
) -> None:
    root, repo = portable_repo
    launcher = root / "Iniciar IA.bat"
    launcher.write_text("launcher personalizado", encoding="utf-8")

    first = _run_setup(root, repo, "-SkipSync")

    _assert_success(first)
    assert launcher.read_text(encoding="utf-8") == "launcher personalizado"
    assert "[CONFLITO]" in first.stdout

    second = _run_setup(root, repo, "-SkipSync", "-Force")

    _assert_success(second)
    generated = launcher.read_text(encoding="utf-8")
    assert f'set "IA_ROOT={root}"' in generated
    assert f'cd /d "{repo}"' in generated


def test_manual_conflict_is_preserved_then_force_restores_only_official_manual(
    portable_repo: tuple[Path, Path],
) -> None:
    root, repo = portable_repo
    official_manual = root / OFFICIAL_MANUAL
    other_manual = root / "Manual_pessoal.docx"
    personalized = b"manual personalizado de teste"
    other_content = b"documento desconhecido preservado"
    official_manual.write_bytes(personalized)
    other_manual.write_bytes(other_content)

    first = _run_setup(root, repo, "-SkipSync")

    _assert_success(first)
    assert official_manual.read_bytes() == personalized
    assert other_manual.read_bytes() == other_content
    assert f"[CONFLITO] Arquivo existente diferente foi preservado: {official_manual}" in (
        first.stdout
    )

    second = _run_setup(root, repo, "-SkipSync", "-Force")

    _assert_success(second)
    assert official_manual.read_bytes() == (
        repo / "workspace_assets" / OFFICIAL_MANUAL
    ).read_bytes()
    assert other_manual.read_bytes() == other_content


def test_second_execution_is_idempotent(
    portable_repo: tuple[Path, Path],
) -> None:
    root, repo = portable_repo

    first = _run_setup(root, repo, "-SkipSync")
    _assert_success(first)
    tracked_files = [
        root / "Iniciar IA.bat",
        root / OFFICIAL_MANUAL,
        repo / ".env",
        *(root / "4_Prompts" / name for name in OFFICIAL_PROMPTS),
    ]
    before = {path: path.read_bytes() for path in tracked_files}

    second = _run_setup(root, repo, "-SkipSync")

    _assert_success(second)
    assert {path: path.read_bytes() for path in tracked_files} == before
    assert second.stdout.count("[IGNORADO] Conteudo identico") == 6
    assert f"[IGNORADO] Conteudo identico: {root / OFFICIAL_MANUAL}" in second.stdout


def test_existing_environment_is_preserved_without_force(
    portable_repo: tuple[Path, Path],
) -> None:
    root, repo = portable_repo
    environment_file = repo / ".env"
    original = b"LOCAL_TEST_VALUE=preserve-me\r\n"
    environment_file.write_bytes(original)

    completed = _run_setup(root, repo, "-SkipSync", "-Force")

    _assert_success(completed)
    assert environment_file.read_bytes() == original
    assert ".env existente foi preservado sem leitura" in completed.stdout


def test_skip_sync_does_not_require_or_call_uv(
    portable_repo: tuple[Path, Path],
) -> None:
    root, repo = portable_repo
    environment = os.environ.copy()
    environment["PATH"] = str(Path(_powershell_executable()).parent)

    completed = _run_setup(
        root,
        repo,
        "-SkipSync",
        environment=environment,
    )

    _assert_success(completed)
    assert "uv sync desabilitado" in completed.stdout


def test_sync_uses_mock_uv_without_network(
    portable_repo: tuple[Path, Path],
    tmp_path: Path,
) -> None:
    root, repo = portable_repo
    fake_bin = tmp_path / "fake-bin"
    fake_bin.mkdir()
    marker = tmp_path / "uv-called.txt"
    (fake_bin / "uv.cmd").write_text(
        '@echo off\r\necho called> "%UV_TEST_MARKER%"\r\nexit /b 0\r\n',
        encoding="ascii",
    )
    environment = os.environ.copy()
    environment["PATH"] = os.pathsep.join(
        (str(fake_bin), environment.get("PATH", ""))
    )
    environment["UV_TEST_MARKER"] = str(marker)

    completed = _run_setup(root, repo, environment=environment)

    _assert_success(completed)
    assert marker.read_text(encoding="utf-8").strip() == "called"
    assert "uv sync concluido" in completed.stdout


def test_incompatible_root_fails_without_moving_repository(
    portable_repo: tuple[Path, Path],
    tmp_path: Path,
) -> None:
    root, repo = portable_repo
    incompatible_root = tmp_path / "other-workspace"

    completed = _run_setup(incompatible_root, repo, "-SkipSync")

    assert completed.returncode != 0
    assert "Estrutura incompativel" in completed.stderr
    assert repo.is_dir()
    assert not (incompatible_root / "2_Entrada").exists()


def test_existing_session_and_usage_are_untouched(
    portable_repo: tuple[Path, Path],
) -> None:
    root, repo = portable_repo
    session = root / "6_Dados" / "sessions" / "existing.json"
    usage = root / "6_Dados" / "usage" / "api_usage.csv"
    session.parent.mkdir(parents=True)
    usage.parent.mkdir(parents=True)
    session_content = b"session sentinel"
    usage_content = b"usage sentinel"
    session.write_bytes(session_content)
    usage.write_bytes(usage_content)

    completed = _run_setup(root, repo, "-SkipSync", "-Force")

    _assert_success(completed)
    assert session.read_bytes() == session_content
    assert usage.read_bytes() == usage_content
