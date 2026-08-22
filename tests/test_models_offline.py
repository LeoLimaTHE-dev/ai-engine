from pathlib import Path

from ai_engine.models import DocumentContent, DocumentImage, DocumentTable


def test_document_image_preserves_binary_payload_and_media_type():
    image = DocumentImage(
        name="sample.png",
        data=b"image-bytes",
        media_type="image/png",
    )

    assert image.name == "sample.png"
    assert image.data == b"image-bytes"
    assert image.media_type == "image/png"


def test_document_table_defaults_to_an_independent_empty_rows_list():
    first = DocumentTable(name="First")
    second = DocumentTable(name="Second")

    first.rows.append(["value"])

    assert first.rows == [["value"]]
    assert second.rows == []


def test_document_content_reports_content_and_path_properties():
    document = DocumentContent(
        source_path=Path("reports/Example.PDF"),
        text="  content  ",
        tables=[DocumentTable(rows=[["cell"]])],
        images=[DocumentImage(name="image.png", data=b"data")],
        metadata={"source": "fixture"},
    )

    assert document.has_text is True
    assert document.has_tables is True
    assert document.has_images is True
    assert document.filename == "Example.PDF"
    assert document.extension == ".pdf"
    assert document.metadata == {"source": "fixture"}


def test_document_content_empty_defaults_and_text_representation():
    document = DocumentContent(source_path=Path("empty.txt"))

    assert document.has_text is False
    assert document.has_tables is False
    assert document.has_images is False
    assert document.to_text() == ""


def test_document_content_to_text_combines_text_table_and_image_marker():
    document = DocumentContent(
        source_path=Path("mixed.docx"),
        text="  Introduction  ",
        tables=[DocumentTable(name="Values", rows=[["A", "10"]])],
        images=[DocumentImage(name="image.png", data=b"data")],
    )

    assert document.to_text() == (
        "Introduction\n\n"
        "[TABLE: Values]\n\n"
        "A | 10\n\n"
        "[IMAGES: 1 embedded]"
    )

