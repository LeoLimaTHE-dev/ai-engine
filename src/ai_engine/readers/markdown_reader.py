from pathlib import Path

from ai_engine.models import DocumentContent


def read_markdown(
    file_path: str | Path,
) -> DocumentContent:
    path = Path(file_path)

    if not path.exists():
        raise FileNotFoundError(f"File not found: {path}")

    if path.suffix.lower() not in (".md", ".markdown"):
        raise ValueError(f"Expected a Markdown file, got: {path.suffix}")

    text = path.read_text(encoding="utf-8")

    return DocumentContent(
        source_path=path,
        text=text,
        metadata={
            "format": "markdown",
            "filename": path.name,
        },
    )
