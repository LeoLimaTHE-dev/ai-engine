from pathlib import Path

import pytest

import ai_engine.batch as batch_module
from ai_engine.models import DocumentContent, DocumentImage, DocumentTable


def make_documents():
    return [
        DocumentContent(
            source_path=Path("first.docx"),
            text=" First text ",
            tables=[
                DocumentTable(
                    rows=[["name", "value"], ["alpha", "10"]],
                    name="Data",
                    source="original-table-source",
                )
            ],
            images=[
                DocumentImage(
                    name="chart.png",
                    data=b"first-image",
                    media_type="image/png",
                )
            ],
        ),
        DocumentContent(
            source_path=Path("second.pdf"),
            text="Second text",
            tables=[DocumentTable(rows=[["beta", "20"]])],
            images=[
                DocumentImage(
                    name="scan.jpg",
                    data=b"second-image",
                    media_type="image/jpeg",
                )
            ],
        ),
    ]


def test_combine_documents_preserves_content_and_source_filenames():
    documents = make_documents()

    combined = batch_module.combine_documents(documents)

    assert combined.source_path == Path("batch")
    assert combined.text == (
        "[DOCUMENT: first.docx]\nFirst text\n\n"
        "[DOCUMENT: second.pdf]\nSecond text"
    )
    assert [table.name for table in combined.tables] == [
        "first.docx - Data",
        "second.pdf - Table 1",
    ]
    assert [table.source for table in combined.tables] == [
        "first.docx",
        "second.pdf",
    ]
    assert [table.rows for table in combined.tables] == [
        [["name", "value"], ["alpha", "10"]],
        [["beta", "20"]],
    ]
    assert [image.name for image in combined.images] == [
        "first_1_chart.png",
        "second_1_scan.jpg",
    ]
    assert [image.data for image in combined.images] == [
        b"first-image",
        b"second-image",
    ]
    assert combined.metadata == {
        "format": "batch",
        "document_count": 2,
        "filenames": ["first.docx", "second.pdf"],
        "image_count": 2,
        "table_count": 2,
    }


def test_combine_documents_rejects_empty_list():
    with pytest.raises(ValueError, match="No documents were provided"):
        batch_module.combine_documents([])


def test_process_batch_individual_calls_once_per_document(monkeypatch):
    documents = make_documents()
    calls = []

    def fake_ask_document(provider, document, prompt):
        calls.append((provider, document, prompt))
        return f"response:{document.filename}"

    monkeypatch.setattr(batch_module, "ask_document", fake_ask_document)

    result = batch_module.process_batch_individual(
        provider="openai",
        documents=documents,
        prompt="Analyze each",
    )

    assert result == {
        "first.docx": "response:first.docx",
        "second.pdf": "response:second.pdf",
    }
    assert calls == [
        ("openai", documents[0], "Analyze each"),
        ("openai", documents[1], "Analyze each"),
    ]


def test_process_batch_consolidated_calls_once_with_combined_document(monkeypatch):
    documents = make_documents()
    calls = []

    def fake_ask_document(provider, document, prompt):
        calls.append((provider, document, prompt))
        return "consolidated-response"

    monkeypatch.setattr(batch_module, "ask_document", fake_ask_document)

    result = batch_module.process_batch_consolidated(
        provider="gemini",
        documents=documents,
        prompt="Compare",
    )

    assert result == "consolidated-response"
    assert len(calls) == 1
    provider, combined, prompt = calls[0]
    assert provider == "gemini"
    assert prompt == "Compare"
    assert combined.source_path == Path("batch")
    assert combined.metadata["filenames"] == ["first.docx", "second.pdf"]


def test_batch_modes_forward_native_structured_when_enabled(monkeypatch):
    documents = make_documents()
    calls = []

    def fake_ask_document(**kwargs):
        calls.append(kwargs)
        return "response"

    monkeypatch.setattr(batch_module, "ask_document", fake_ask_document)

    batch_module.process_batch_individual(
        provider="openai",
        documents=documents,
        prompt="Analyze",
        native_structured=True,
    )
    batch_module.process_batch_consolidated(
        provider="openai",
        documents=documents,
        prompt="Analyze",
        native_structured=True,
    )

    assert len(calls) == 3
    assert all(call["native_structured"] is True for call in calls)
