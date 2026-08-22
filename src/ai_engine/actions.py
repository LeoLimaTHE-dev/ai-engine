from pathlib import Path

from .exporters import (
    save_output,
    save_xlsx_tables,
)
from .results import (
    OutputRequest,
    StructuredResult,
)

SUPPORTED_FORMATS = {
    "txt",
    "md",
    "docx",
    "pdf",
    "xlsx",
}


def sanitize_filename(
    filename: str,
) -> str:
    """
    Prevents the model from writing outside
    the configured output directory.
    """

    return Path(filename).name


def execute_output(
    output: OutputRequest,
    output_dir: str | Path,
) -> Path:
    output_dir = Path(output_dir)

    output_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    format_name = output.format.lower().lstrip(".")

    if format_name not in SUPPORTED_FORMATS:
        raise ValueError(f"Unsupported output format: {format_name}")

    filename = sanitize_filename(output.filename)

    expected_extension = f".{format_name}"

    if not filename.lower().endswith(expected_extension):
        filename += expected_extension

    path = output_dir / filename

    if format_name == "xlsx" and output.tables:
        return save_xlsx_tables(
            tables=output.tables,
            output_path=path,
        )

    return save_output(
        content=output.content or "",
        output_path=path,
        title=output.title,
    )


def execute_structured_result(
    result: StructuredResult,
    output_dir: str | Path,
) -> list[Path]:
    created_files: list[Path] = []

    for output in result.outputs:
        created_files.append(
            execute_output(
                output=output,
                output_dir=output_dir,
            )
        )

    return created_files
