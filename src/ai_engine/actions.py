from pathlib import Path

from .exporters import (
    save_output,
    save_xlsx_tables,
)
from .results import (
    OutputRequest,
    ResultTable,
    StructuredResult,
)
from .structured_errors import OutputExecutionError
from .structured_planning import PlannedOutput, plan_structured_outputs

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
    *,
    overwrite: bool = True,
) -> list[Path]:
    plan = plan_structured_outputs(
        result=result,
        output_dir=output_dir,
        overwrite=overwrite,
    )
    created_files: list[Path] = []

    for output_index, planned in enumerate(plan.outputs):
        try:
            created_files.append(_execute_planned_output(planned))
        except Exception as exc:
            raise OutputExecutionError(
                f"failed to write planned output {planned.path}",
                field_path=f"outputs[{output_index}]",
                details={"path": str(planned.path)},
            ) from exc

    return created_files


def _execute_planned_output(
    planned: PlannedOutput,
) -> Path:
    original = planned.original

    if planned.format == "xlsx" and planned.tables:
        prepared_tables = [
            ResultTable(
                name=planned_table.sheet_name,
                headers=planned_table.original.headers,
                rows=planned_table.original.rows,
            )
            for planned_table in planned.tables
        ]

        return save_xlsx_tables(
            tables=prepared_tables,
            output_path=planned.path,
        )

    return save_output(
        content=original.content or "",
        output_path=planned.path,
        title=original.title,
    )
