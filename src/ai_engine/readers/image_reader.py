import mimetypes
from pathlib import Path

from ai_engine.models import (
    DocumentContent,
    DocumentImage,
)

SUPPORTED_IMAGE_EXTENSIONS = {
    ".png",
    ".jpg",
    ".jpeg",
    ".webp",
    ".bmp",
    ".gif",
    ".tiff",
    ".tif",
}


def read_image(
    file_path: str | Path,
) -> DocumentContent:
    path = Path(file_path)

    if not path.exists():
        raise FileNotFoundError(f"File not found: {path}")

    extension = path.suffix.lower()

    if extension not in SUPPORTED_IMAGE_EXTENSIONS:
        raise ValueError(f"Unsupported image type: {extension}")

    image_data = path.read_bytes()

    media_type, _ = mimetypes.guess_type(path.name)

    image = DocumentImage(
        name=path.name,
        data=image_data,
        media_type=media_type,
    )

    return DocumentContent(
        source_path=path,
        images=[image],
        metadata={
            "format": extension.lstrip("."),
            "filename": path.name,
            "image_count": 1,
        },
    )
