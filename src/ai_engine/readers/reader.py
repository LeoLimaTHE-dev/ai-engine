from pathlib import Path

from ai_engine.models import DocumentContent

from .csv_reader import read_csv
from .docx_reader import read_docx
from .image_reader import read_image
from .markdown_reader import read_markdown
from .pdf_reader import read_pdf
from .text_reader import read_text
from .xlsx_reader import read_xlsx


def read_document(
    file_path: str | Path,
) -> DocumentContent:
    path = Path(file_path)

    if not path.exists():
        raise FileNotFoundError(f"File not found: {path}")

    extension = path.suffix.lower()

    readers = {
        ".txt": read_text,
        ".md": read_markdown,
        ".markdown": read_markdown,
        ".csv": read_csv,
        ".docx": read_docx,
        ".pdf": read_pdf,
        ".xlsx": read_xlsx,
        ".xlsm": read_xlsx,
        ".png": read_image,
        ".jpg": read_image,
        ".jpeg": read_image,
        ".webp": read_image,
        ".bmp": read_image,
        ".gif": read_image,
        ".tiff": read_image,
        ".tif": read_image,
    }

    reader = readers.get(extension)

    if reader is None:
        raise ValueError(f"Unsupported file type: {extension}")

    return reader(path)


def read_documents(
    file_paths: list[str | Path],
) -> list[DocumentContent]:
    documents: list[DocumentContent] = []

    for file_path in file_paths:
        documents.append(read_document(file_path))

    return documents
