from pathlib import Path

from ai_engine.models import (
    DocumentContent,
    DocumentImage,
    DocumentTable,
)

from .multimodal import ask_document


def combine_documents(
    documents: list[DocumentContent],
) -> DocumentContent:
    """
    Combines multiple DocumentContent objects into
    one virtual document for consolidated analysis.
    """

    if not documents:
        raise ValueError("No documents were provided.")

    text_parts: list[str] = []
    tables: list[DocumentTable] = []
    images: list[DocumentImage] = []

    filenames: list[str] = []

    for document in documents:
        filenames.append(document.filename)

        # -------------------------
        # Text
        # -------------------------

        if document.text.strip():
            text_parts.append(
                f"[DOCUMENT: {document.filename}]\n{document.text.strip()}"
            )

        # -------------------------
        # Tables
        # -------------------------

        for table_index, table in enumerate(
            document.tables,
            start=1,
        ):
            table_name = table.name or f"Table {table_index}"

            tables.append(
                DocumentTable(
                    rows=table.rows,
                    name=(f"{document.filename} - {table_name}"),
                    source=document.filename,
                )
            )

        # -------------------------
        # Images
        # -------------------------

        for image_index, image in enumerate(
            document.images,
            start=1,
        ):
            image_name = image.name

            if image.name != document.filename:
                image_name = f"{document.source_path.stem}_{image_index}_{image.name}"

            images.append(
                DocumentImage(
                    name=image_name,
                    data=image.data,
                    media_type=image.media_type,
                )
            )

    return DocumentContent(
        source_path=Path("batch"),
        text="\n\n".join(text_parts),
        tables=tables,
        images=images,
        metadata={
            "format": "batch",
            "document_count": len(documents),
            "filenames": filenames,
            "image_count": len(images),
            "table_count": len(tables),
        },
    )


def process_batch_individual(
    provider: str,
    documents: list[DocumentContent],
    prompt: str,
    *,
    native_structured: bool = False,
) -> dict[str, str]:
    """
    Processes each document separately.

    Returns:
        {
            "file1.docx": "AI response...",
            "file2.pdf": "AI response...",
        }
    """

    results: dict[str, str] = {}

    for document in documents:
        call_kwargs = {
            "provider": provider,
            "document": document,
            "prompt": prompt,
        }

        if native_structured:
            call_kwargs["native_structured"] = True

        result = ask_document(**call_kwargs)

        results[document.filename] = result

    return results


def process_batch_consolidated(
    provider: str,
    documents: list[DocumentContent],
    prompt: str,
    *,
    native_structured: bool = False,
) -> str:
    """
    Combines all documents and sends them
    together for one consolidated analysis.
    """

    combined = combine_documents(documents)

    call_kwargs = {
        "provider": provider,
        "document": combined,
        "prompt": prompt,
    }

    if native_structured:
        call_kwargs["native_structured"] = True

    return ask_document(**call_kwargs)
