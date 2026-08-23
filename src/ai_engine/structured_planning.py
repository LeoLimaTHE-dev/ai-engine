from dataclasses import dataclass
from pathlib import Path
import re

from .results import OutputRequest, ResultTable, StructuredResult
from .structured_errors import OutputValidationError
from .structured_validation import validate_structured_result

MAX_FILENAME_LENGTH = 255
MAX_SHEET_NAME_LENGTH = 31

_INVALID_FILENAME_CHARACTERS = frozenset('<>:"/\\|?*')
_INVALID_SHEET_CHARACTERS = re.compile(r"[:\\/?*\[\]]")
_WINDOWS_RESERVED_STEMS = frozenset(
    {
        "CON",
        "PRN",
        "AUX",
        "NUL",
        *(f"COM{number}" for number in range(1, 10)),
        *(f"LPT{number}" for number in range(1, 10)),
    }
)


@dataclass(frozen=True, slots=True)
class PlannedTable:
    original: ResultTable
    sheet_name: str


@dataclass(frozen=True, slots=True)
class PlannedOutput:
    original: OutputRequest
    format: str
    filename: str
    path: Path
    tables: tuple[PlannedTable, ...] = ()


@dataclass(frozen=True, slots=True)
class StructuredOutputPlan:
    output_dir: Path
    outputs: tuple[PlannedOutput, ...]
    overwrite: bool


def _fail(field_path: str, message: str, *, details: object | None = None) -> None:
    raise OutputValidationError(
        message,
        field_path=field_path,
        details=details,
    )


def _portable_basename(filename: str) -> str:
    return filename.replace("\\", "/").rsplit("/", 1)[-1]


def _plan_filename(output: OutputRequest, output_index: int) -> tuple[str, str]:
    field_path = f"outputs[{output_index}].filename"
    normalized_format = output.format.lower().lstrip(".")
    basename = _portable_basename(output.filename)

    if basename.endswith((" ", ".")):
        _fail(field_path, "filename cannot end with a space or dot")

    source_path = Path(basename)
    source_stem = source_path.stem if source_path.suffix else basename
    final_filename = f"{source_stem}.{normalized_format}"
    final_stem = Path(final_filename).stem

    if final_stem.endswith((" ", ".")):
        _fail(field_path, "filename stem cannot end with a space or dot")

    invalid_characters = sorted(
        character
        for character in set(final_filename)
        if character in _INVALID_FILENAME_CHARACTERS
    )

    if invalid_characters:
        _fail(
            field_path,
            f"filename contains invalid characters: {''.join(invalid_characters)!r}",
        )

    if final_stem.upper() in _WINDOWS_RESERVED_STEMS:
        _fail(field_path, f"reserved Windows filename {final_stem!r}")

    if len(final_filename) > MAX_FILENAME_LENGTH:
        _fail(
            field_path,
            f"filename exceeds {MAX_FILENAME_LENGTH} characters",
        )

    return normalized_format, final_filename


def _unique_sheet_name(
    raw_name: str,
    table_index: int,
    used_names: set[str],
) -> str:
    fallback = f"Table {table_index + 1}"
    normalized = _INVALID_SHEET_CHARACTERS.sub("_", raw_name or fallback)
    base_name = normalized[:MAX_SHEET_NAME_LENGTH] or fallback
    candidate = base_name
    suffix_number = 2

    while candidate.casefold() in used_names:
        suffix = f"_{suffix_number}"
        candidate = f"{base_name[: MAX_SHEET_NAME_LENGTH - len(suffix)]}{suffix}"
        suffix_number += 1

    used_names.add(candidate.casefold())
    return candidate


def _plan_tables(
    output: OutputRequest,
) -> tuple[PlannedTable, ...]:
    used_names: set[str] = set()
    planned_tables: list[PlannedTable] = []

    for table_index, table in enumerate(output.tables):
        planned_tables.append(
            PlannedTable(
                original=table,
                sheet_name=_unique_sheet_name(
                    table.name,
                    table_index,
                    used_names,
                ),
            )
        )

    return tuple(planned_tables)


def plan_structured_outputs(
    result: StructuredResult,
    output_dir: str | Path,
    *,
    overwrite: bool = True,
) -> StructuredOutputPlan:
    validate_structured_result(result)

    base_dir = Path(output_dir)
    planned_outputs: list[PlannedOutput] = []
    planned_paths: dict[str, int] = {}

    for output_index, output in enumerate(result.outputs):
        normalized_format, final_filename = _plan_filename(output, output_index)
        final_path = base_dir / final_filename
        collision_key = final_filename.casefold()

        if collision_key in planned_paths:
            previous_index = planned_paths[collision_key]
            _fail(
                f"outputs[{output_index}].filename",
                (
                    f"planned path {final_filename!r} collides with "
                    f"outputs[{previous_index}].filename"
                ),
                details={"other_output_index": previous_index},
            )

        if not overwrite and final_path.exists():
            _fail(
                f"outputs[{output_index}].filename",
                f"output already exists: {final_path}",
            )

        planned_paths[collision_key] = output_index
        planned_outputs.append(
            PlannedOutput(
                original=output,
                format=normalized_format,
                filename=final_filename,
                path=final_path,
                tables=_plan_tables(output) if normalized_format == "xlsx" else (),
            )
        )

    return StructuredOutputPlan(
        output_dir=base_dir,
        outputs=tuple(planned_outputs),
        overwrite=overwrite,
    )
