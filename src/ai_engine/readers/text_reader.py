from pathlib import Path

from ai_engine.models import DocumentContent


def read_text(
    file_path: str | Path,
) -> DocumentContent:
    path = Path(file_path)

    if not path.exists():
        raise FileNotFoundError(f"File not found: {path}")

    text = path.read_text(encoding="utf-8")

    return DocumentContent(
        source_path=path,
        text=text,
        metadata={
            "format": "txt",
            "filename": path.name,
        },
    )
