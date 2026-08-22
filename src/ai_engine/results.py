from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class ResultTable:
    name: str
    headers: list[str] = field(default_factory=list)
    rows: list[list[str]] = field(default_factory=list)


@dataclass
class OutputRequest:
    format: str
    filename: str
    title: str | None = None
    content: str | None = None
    tables: list[ResultTable] = field(default_factory=list)


@dataclass
class StructuredResult:
    message: str
    outputs: list[OutputRequest] = field(default_factory=list)

    @property
    def has_outputs(self) -> bool:
        return bool(self.outputs)

    def output_count(self) -> int:
        return len(self.outputs)

    def output_paths(
        self,
        output_dir: str | Path,
    ) -> list[Path]:
        base = Path(output_dir)

        return [base / output.filename for output in self.outputs]
