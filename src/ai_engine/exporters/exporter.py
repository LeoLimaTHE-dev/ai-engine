from pathlib import Path

from .docx_exporter import save_docx
from .pdf_exporter import save_pdf
from .text_exporter import save_text
from .xlsx_exporter import save_xlsx

SUPPORTED_OUTPUT_EXTENSIONS = {
    ".txt",
    ".md",
    ".docx",
    ".pdf",
    ".xlsx",
}


def save_output(
    content: str,
    output_path: str | Path,
    title: str | None = None,
) -> Path:
    path = Path(output_path)

    extension = path.suffix.lower()

    if extension not in SUPPORTED_OUTPUT_EXTENSIONS:
        raise ValueError(f"Unsupported output format: {extension}")

    if extension in (
        ".txt",
        ".md",
    ):
        return save_text(
            content,
            path,
        )

    if extension == ".docx":
        return save_docx(
            content,
            path,
            title=title,
        )

    if extension == ".pdf":
        return save_pdf(
            content,
            path,
            title=title,
        )

    if extension == ".xlsx":
        return save_xlsx(
            content,
            path,
            title=(title or "AI Result"),
        )

    raise ValueError(f"No exporter available for: {extension}")
