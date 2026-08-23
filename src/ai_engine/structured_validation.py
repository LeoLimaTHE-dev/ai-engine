from pathlib import Path

from .results import OutputRequest, ResultTable, StructuredResult
from .structured_errors import OutputValidationError

SUPPORTED_STRUCTURED_FORMATS = {
    "txt",
    "md",
    "docx",
    "pdf",
    "xlsx",
}


def _fail(field_path: str, message: str) -> None:
    raise OutputValidationError(
        message,
        field_path=field_path,
    )


def _validate_table(table: ResultTable, field_path: str) -> None:
    if not isinstance(table.name, str):
        _fail(f"{field_path}.name", "expected str")

    if not isinstance(table.headers, list):
        _fail(f"{field_path}.headers", "expected list[str]")

    for header_index, header in enumerate(table.headers):
        if not isinstance(header, str):
            _fail(f"{field_path}.headers[{header_index}]", "expected str")

    if not isinstance(table.rows, list):
        _fail(f"{field_path}.rows", "expected list[list[str]]")

    expected_width = len(table.headers) if table.headers else None

    for row_index, row in enumerate(table.rows):
        row_path = f"{field_path}.rows[{row_index}]"

        if not isinstance(row, list):
            _fail(row_path, "expected list[str]")

        if expected_width is None:
            expected_width = len(row)
        elif len(row) != expected_width:
            _fail(
                row_path,
                f"expected {expected_width} cells, got {len(row)}",
            )

        for cell_index, cell in enumerate(row):
            if not isinstance(cell, str):
                _fail(f"{row_path}[{cell_index}]", "expected str")


def _validate_output(output: OutputRequest, field_path: str) -> None:
    if not isinstance(output.format, str):
        _fail(f"{field_path}.format", "expected str")

    normalized_format = output.format.lower().lstrip(".")

    if normalized_format not in SUPPORTED_STRUCTURED_FORMATS:
        _fail(
            f"{field_path}.format",
            f"unsupported format {output.format!r}",
        )

    if not isinstance(output.filename, str):
        _fail(f"{field_path}.filename", "expected str")

    stripped_filename = output.filename.strip()

    if not stripped_filename:
        _fail(f"{field_path}.filename", "filename cannot be empty")

    basename = Path(stripped_filename).name

    if not basename or basename in {".", ".."}:
        _fail(f"{field_path}.filename", "filename must have a valid basename")

    if output.title is not None and not isinstance(output.title, str):
        _fail(f"{field_path}.title", "expected str or None")

    if output.content is not None and not isinstance(output.content, str):
        _fail(f"{field_path}.content", "expected str or None")

    if not isinstance(output.tables, list):
        _fail(f"{field_path}.tables", "expected list[ResultTable]")

    if normalized_format != "xlsx" and output.tables:
        _fail(
            f"{field_path}.tables",
            f"tables are not supported for format {normalized_format!r}",
        )

    for table_index, table in enumerate(output.tables):
        table_path = f"{field_path}.tables[{table_index}]"

        if not isinstance(table, ResultTable):
            _fail(table_path, "expected ResultTable")

        _validate_table(table, table_path)


def validate_structured_result(result: StructuredResult) -> StructuredResult:
    if not isinstance(result, StructuredResult):
        _fail("result", "expected StructuredResult")

    if not isinstance(result.message, str):
        _fail("message", "expected str")

    if not isinstance(result.outputs, list):
        _fail("outputs", "expected list[OutputRequest]")

    for output_index, output in enumerate(result.outputs):
        output_path = f"outputs[{output_index}]"

        if not isinstance(output, OutputRequest):
            _fail(output_path, "expected OutputRequest")

        _validate_output(output, output_path)

    return result
