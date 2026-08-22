from pathlib import Path

from ai_engine.models import DocumentContent, DocumentTable


def test_to_text_includes_each_table_row_once():
    document = DocumentContent(
        source_path=Path("example.csv"),
        tables=[
            DocumentTable(
                name="Data",
                rows=[
                    ["name", "value"],
                    ["alpha", "10"],
                ],
            )
        ],
    )

    result = document.to_text()

    assert result.count("name | value") == 1
    assert result.count("alpha | 10") == 1

