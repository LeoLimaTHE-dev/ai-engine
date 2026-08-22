import os
from dataclasses import dataclass
from pathlib import Path


DEFAULT_IA_ROOT = Path(r"C:\IA")


@dataclass(frozen=True, slots=True)
class OperationalPaths:
    root: Path
    input_dir: Path
    output_dir: Path
    prompts_dir: Path
    models_dir: Path
    data_dir: Path
    sessions_dir: Path
    usage_dir: Path
    temp_dir: Path


def _validate_root(value: str | Path) -> Path:
    raw_value = str(value)

    if not raw_value.strip():
        raise ValueError("IA root cannot be empty.")

    root = Path(value)

    if not root.is_absolute():
        raise ValueError("IA root must be an absolute path.")

    return root


def get_paths(
    root: str | Path | None = None,
) -> OperationalPaths:
    if root is None:
        environment_root = os.environ.get("IA_ROOT")
        root = DEFAULT_IA_ROOT if environment_root is None else environment_root

    resolved_root = _validate_root(root)
    data_dir = resolved_root / "6_Dados"

    return OperationalPaths(
        root=resolved_root,
        input_dir=resolved_root / "2_Entrada",
        output_dir=resolved_root / "3_Saída",
        prompts_dir=resolved_root / "4_Prompts",
        models_dir=resolved_root / "5_Modelos",
        data_dir=data_dir,
        sessions_dir=data_dir / "sessions",
        usage_dir=data_dir / "usage",
        temp_dir=resolved_root / "7_Temporario",
    )
