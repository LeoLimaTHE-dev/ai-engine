import csv
from pathlib import Path

from ai_engine.models import (
    DocumentContent,
    DocumentTable,
)


def read_csv(
    file_path: str | Path,
) -> DocumentContent:
    path = Path(file_path)

    if not path.exists():
        raise FileNotFoundError(f"File not found: {path}")

    if path.suffix.lower() != ".csv":
        raise ValueError(f"Expected a .csv file, got: {path.suffix}")

    rows: list[list[str]] = []

    with path.open(
        "r",
        encoding="utf-8-sig",
        newline="",
    ) as file:
        sample = file.read(4096)

        file.seek(0)

        try:
            dialect = csv.Sniffer().sniff(sample)

            reader = csv.reader(
                file,
                dialect,
            )

        except csv.Error:
            reader = csv.reader(file)

        for row in reader:
            rows.append([cell.strip() for cell in row])

    table = DocumentTable(
        rows=rows,
        name=path.stem,
        source=path.name,
    )

    return DocumentContent(
        source_path=path,
        tables=[table],
        metadata={
            "format": "csv",
            "filename": path.name,
            "row_count": len(rows),
        },
    )
