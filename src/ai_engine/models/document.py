from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class DocumentImage:
    name: str
    data: bytes
    media_type: str | None = None


@dataclass
class DocumentTable:
    rows: list[list[str]] = field(default_factory=list)
    name: str | None = None
    source: str | None = None


@dataclass
class DocumentContent:
    source_path: Path

    text: str = ""

    tables: list[DocumentTable] = field(default_factory=list)

    images: list[DocumentImage] = field(default_factory=list)

    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def has_text(self) -> bool:
        return bool(self.text.strip())

    @property
    def has_tables(self) -> bool:
        return bool(self.tables)

    @property
    def has_images(self) -> bool:
        return bool(self.images)

    @property
    def filename(self) -> str:
        return self.source_path.name

    @property
    def extension(self) -> str:
        return self.source_path.suffix.lower()

    def to_text(self) -> str:
        """
        Produces a text representation suitable for
        prompts and debugging.

        Images themselves are not converted to text here.
        """

        parts: list[str] = []

        if self.text.strip():
            parts.append(self.text.strip())

        for index, table in enumerate(
            self.tables,
            start=1,
        ):
            table_name = table.name or f"Table {index}"

            parts.append(f"[TABLE: {table_name}]")

            for row in table.rows:
                parts.append(" | ".join(row))

        if self.images:
            parts.append(f"[IMAGES: {len(self.images)} embedded]")

        return "\n\n".join(parts)
