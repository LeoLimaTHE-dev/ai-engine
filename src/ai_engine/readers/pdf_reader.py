from pathlib import Path

import pymupdf

from ai_engine.models import (
    DocumentContent,
    DocumentImage,
)

MIN_TEXT_CHARS_PER_PAGE = 30


def read_pdf(
    file_path: str | Path,
) -> DocumentContent:
    path = Path(file_path)

    if not path.exists():
        raise FileNotFoundError(f"File not found: {path}")

    if path.suffix.lower() != ".pdf":
        raise ValueError(f"Expected a .pdf file, got: {path.suffix}")

    document = pymupdf.open(path)

    text_parts: list[str] = []
    images: list[DocumentImage] = []

    page_text_lengths: list[int] = []

    pages_with_text = 0
    pages_without_text = 0
    rendered_page_count = 0

    for page_index, page in enumerate(
        document,
        start=1,
    ):
        page_text = page.get_text().strip()

        text_length = len(page_text)

        is_page_scanned = text_length < MIN_TEXT_CHARS_PER_PAGE

        page_text_lengths.append(text_length)

        if text_length >= MIN_TEXT_CHARS_PER_PAGE:
            pages_with_text += 1
        else:
            pages_without_text += 1

        # -------------------------
        # Extract digital text
        # -------------------------

        if page_text:
            text_parts.append(f"[PAGE {page_index}]\n{page_text}")

        # -------------------------
        # Extract embedded images
        # -------------------------

        for image_index, image_info in enumerate(
            page.get_images(full=True),
            start=1,
        ):
            xref = image_info[0]

            image_data = document.extract_image(xref)

            image_bytes = image_data["image"]
            image_ext = image_data["ext"]

            image_name = f"page_{page_index}_image_{image_index}.{image_ext}"

            media_type = f"image/{image_ext}"

            images.append(
                DocumentImage(
                    name=image_name,
                    data=image_bytes,
                    media_type=media_type,
                )
            )

        # -------------------------
        # Render scanned pages
        # -------------------------

        if is_page_scanned:
            pixmap = page.get_pixmap(
                dpi=150,
                alpha=False,
            )

            page_image = pixmap.tobytes("png")

            images.append(
                DocumentImage(
                    name=(f"page_{page_index}_render.png"),
                    data=page_image,
                    media_type="image/png",
                )
            )

            rendered_page_count += 1

    # -------------------------
    # Document classification
    # -------------------------

    page_count = len(document)

    if page_count == 0:
        document_type = "empty"

    elif pages_with_text == page_count:
        document_type = "digital"

    elif pages_with_text == 0:
        document_type = "scanned"

    else:
        document_type = "mixed"

    # -------------------------
    # PDF metadata
    # -------------------------

    metadata = document.metadata or {}

    # -------------------------
    # Result
    # -------------------------

    result = DocumentContent(
        source_path=path,
        text="\n\n".join(text_parts),
        images=images,
        metadata={
            "format": "pdf",
            "filename": path.name,
            "page_count": page_count,
            "image_count": len(images),
            "document_type": document_type,
            "is_scanned": (document_type == "scanned"),
            "is_mixed": (document_type == "mixed"),
            "pages_with_text": (pages_with_text),
            "pages_without_text": (pages_without_text),
            "rendered_page_count": (rendered_page_count),
            "page_text_lengths": (page_text_lengths),
            "title": metadata.get("title"),
            "author": metadata.get("author"),
        },
    )

    document.close()

    return result
