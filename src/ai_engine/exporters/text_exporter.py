from pathlib import Path


def save_text(
    content: str,
    output_path: str | Path,
) -> Path:
    path = Path(output_path)

    path.parent.mkdir(parents=True, exist_ok=True)

    path.write_text(content, encoding="utf-8")

    return path
