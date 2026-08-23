from pathlib import Path

import pytest

from ai_engine.results import OutputRequest, ResultTable, StructuredResult
from ai_engine.structured_errors import OutputValidationError
from ai_engine.structured_planning import (
    MAX_FILENAME_LENGTH,
    MAX_SHEET_NAME_LENGTH,
    PlannedOutput,
    PlannedTable,
    StructuredOutputPlan,
    plan_structured_outputs,
)


def make_result(*outputs):
    return StructuredResult(message="Done", outputs=list(outputs))


def make_output(format="txt", filename="result.txt", **kwargs):
    return OutputRequest(format=format, filename=filename, **kwargs)


def plan_one(tmp_path, output, *, overwrite=True):
    return plan_structured_outputs(
        make_result(output),
        tmp_path,
        overwrite=overwrite,
    ).outputs[0]


def test_empty_result_produces_empty_plan(tmp_path):
    plan = plan_structured_outputs(StructuredResult(message=""), tmp_path)

    assert plan == StructuredOutputPlan(
        output_dir=tmp_path,
        outputs=(),
        overwrite=True,
    )


def test_valid_output_produces_planned_output_with_original_reference(tmp_path):
    output = make_output(content="content")
    planned = plan_one(tmp_path, output)

    assert isinstance(planned, PlannedOutput)
    assert planned.original is output
    assert planned.path == tmp_path / "result.txt"


@pytest.mark.parametrize(
    ("format_name", "expected"),
    [("TXT", "txt"), (".PDF", "pdf"), ("XLSX", "xlsx")],
)
def test_format_is_normalized_in_plan_only(format_name, expected, tmp_path):
    output = make_output(format=format_name, filename="result")

    planned = plan_one(tmp_path, output)

    assert planned.format == expected
    assert output.format == format_name


def test_output_directory_is_preserved_as_path(tmp_path):
    output_dir = tmp_path / "not-created"
    plan = plan_structured_outputs(make_result(), str(output_dir))

    assert plan.output_dir == output_dir
    assert not output_dir.exists()


@pytest.mark.parametrize(
    ("filename", "format_name", "expected"),
    [
        ("report", "pdf", "report.pdf"),
        ("report.pdf", "pdf", "report.pdf"),
        ("report.docx", "pdf", "report.pdf"),
        ("report.final.docx", "pdf", "report.final.pdf"),
    ],
)
def test_final_extension_is_determined_by_format(
    filename,
    format_name,
    expected,
    tmp_path,
):
    planned = plan_one(tmp_path, make_output(format=format_name, filename=filename))

    assert planned.filename == expected
    assert planned.path == tmp_path / expected


@pytest.mark.parametrize(
    ("filename", "expected"),
    [
        ("../../report.txt", "report.txt"),
        (r"..\..\report.txt", "report.txt"),
        (r"C:\temp\report.txt", "report.txt"),
        ("/tmp/report.txt", "report.txt"),
        ("folder/sub/report.txt", "report.txt"),
    ],
)
def test_posix_and_windows_paths_are_reduced_to_portable_basename(
    filename,
    expected,
    tmp_path,
):
    planned = plan_one(tmp_path, make_output(filename=filename))

    assert planned.filename == expected
    assert planned.path.parent == tmp_path


@pytest.mark.parametrize(
    "filename",
    ["CON", "con.txt", "AUX.pdf", "NUL", "COM1.docx", "com9.txt", "LPT1.xlsx", "lpt9.md"],
)
def test_windows_reserved_filename_stems_are_rejected_everywhere(filename, tmp_path):
    with pytest.raises(OutputValidationError) as captured:
        plan_one(tmp_path, make_output(filename=filename))

    assert captured.value.field_path == "outputs[0].filename"
    assert "reserved Windows filename" in str(captured.value)


@pytest.mark.parametrize("filename", ['bad<name.txt', 'bad:name.txt', 'bad"name.txt', "bad|name.txt", "bad?name.txt", "bad*name.txt"])
def test_invalid_windows_filename_characters_are_rejected(filename, tmp_path):
    with pytest.raises(OutputValidationError) as captured:
        plan_one(tmp_path, make_output(filename=filename))

    assert captured.value.field_path == "outputs[0].filename"
    assert "invalid characters" in str(captured.value)


@pytest.mark.parametrize("filename", ["report ", "report.", "report .txt", "report..txt"])
def test_terminal_space_or_dot_in_filename_or_stem_is_rejected(filename, tmp_path):
    with pytest.raises(OutputValidationError) as captured:
        plan_one(tmp_path, make_output(filename=filename))

    assert captured.value.field_path == "outputs[0].filename"
    assert "space or dot" in str(captured.value)


def test_filename_longer_than_255_characters_is_rejected(tmp_path):
    filename = f"{'a' * 252}.txt"

    with pytest.raises(OutputValidationError, match="exceeds 255 characters"):
        plan_one(tmp_path, make_output(filename=filename))


def test_filename_exactly_255_characters_is_accepted(tmp_path):
    filename = f"{'a' * 251}.txt"
    planned = plan_one(tmp_path, make_output(filename=filename))

    assert len(planned.filename) == MAX_FILENAME_LENGTH


def test_distinct_outputs_do_not_collide(tmp_path):
    plan = plan_structured_outputs(
        make_result(
            make_output(filename="one.txt"),
            make_output(filename="two.txt"),
        ),
        tmp_path,
    )

    assert [output.filename for output in plan.outputs] == ["one.txt", "two.txt"]


def test_same_basename_after_sanitization_is_rejected(tmp_path):
    result = make_result(
        make_output(filename="a/report.txt"),
        make_output(filename="b/report.txt"),
    )

    with pytest.raises(OutputValidationError) as captured:
        plan_structured_outputs(result, tmp_path)

    assert captured.value.field_path == "outputs[1].filename"
    assert "outputs[0].filename" in str(captured.value)


def test_collision_after_extension_replacement_is_rejected(tmp_path):
    result = make_result(
        make_output(format="pdf", filename="report.docx"),
        make_output(format="pdf", filename="report.pdf"),
    )

    with pytest.raises(OutputValidationError, match="collides"):
        plan_structured_outputs(result, tmp_path)


def test_output_collisions_are_case_insensitive(tmp_path):
    result = make_result(
        make_output(filename="Report.txt"),
        make_output(filename="report.txt"),
    )

    with pytest.raises(OutputValidationError, match="collides"):
        plan_structured_outputs(result, tmp_path)


def test_overwrite_true_allows_existing_file_without_modifying_it(tmp_path):
    existing = tmp_path / "result.txt"
    existing.write_text("original", encoding="utf-8")

    planned = plan_one(tmp_path, make_output(content="replacement"), overwrite=True)

    assert planned.path == existing
    assert existing.read_text(encoding="utf-8") == "original"


def test_overwrite_false_rejects_existing_file_without_modifying_it(tmp_path):
    existing = tmp_path / "result.txt"
    existing.write_text("original", encoding="utf-8")

    with pytest.raises(OutputValidationError) as captured:
        plan_one(tmp_path, make_output(), overwrite=False)

    assert captured.value.field_path == "outputs[0].filename"
    assert "already exists" in str(captured.value)
    assert existing.read_text(encoding="utf-8") == "original"


def xlsx_output(*tables):
    return make_output(format="xlsx", filename="data.xlsx", tables=list(tables))


def test_xlsx_normal_sheet_name_is_preserved(tmp_path):
    table = ResultTable(name="Data")
    planned = plan_one(tmp_path, xlsx_output(table))

    assert planned.tables == (PlannedTable(original=table, sheet_name="Data"),)


def test_empty_xlsx_sheet_names_use_table_number(tmp_path):
    planned = plan_one(
        tmp_path,
        xlsx_output(ResultTable(name=""), ResultTable(name="")),
    )

    assert [table.sheet_name for table in planned.tables] == ["Table 1", "Table 2"]


def test_invalid_xlsx_sheet_characters_are_replaced_with_underscore(tmp_path):
    planned = plan_one(tmp_path, xlsx_output(ResultTable(name=r"A:B\C/D?E*F[G]")))

    assert planned.tables[0].sheet_name == "A_B_C_D_E_F_G_"


def test_xlsx_sheet_name_is_truncated_to_31_characters(tmp_path):
    planned = plan_one(tmp_path, xlsx_output(ResultTable(name="A" * 40)))

    assert planned.tables[0].sheet_name == "A" * MAX_SHEET_NAME_LENGTH


@pytest.mark.parametrize(
    ("names", "expected"),
    [
        (["Data", "Data"], ["Data", "Data_2"]),
        (["Data", "Data", "Data"], ["Data", "Data_2", "Data_3"]),
        (["Data", "data"], ["Data", "data_2"]),
    ],
)
def test_xlsx_sheet_collisions_are_deduplicated_case_insensitively(
    names,
    expected,
    tmp_path,
):
    planned = plan_one(
        tmp_path,
        xlsx_output(*(ResultTable(name=name) for name in names)),
    )

    assert [table.sheet_name for table in planned.tables] == expected


def test_xlsx_collision_after_truncation_is_deduplicated(tmp_path):
    shared_prefix = "A" * 31
    planned = plan_one(
        tmp_path,
        xlsx_output(
            ResultTable(name=f"{shared_prefix} first"),
            ResultTable(name=f"{shared_prefix} second"),
        ),
    )

    assert [table.sheet_name for table in planned.tables] == [
        shared_prefix,
        f"{'A' * 29}_2",
    ]
    assert all(len(table.sheet_name) <= 31 for table in planned.tables)


def test_planning_does_not_mutate_original_output_or_table(tmp_path):
    table = ResultTable(name="Financeiro/2026")
    output = make_output(format="XLSX", filename=r"folder\Report.DOCX", tables=[table])

    planned = plan_one(tmp_path, output)

    assert planned.format == "xlsx"
    assert planned.filename == "Report.xlsx"
    assert planned.tables[0].sheet_name == "Financeiro_2026"
    assert output.format == "XLSX"
    assert output.filename == r"folder\Report.DOCX"
    assert table.name == "Financeiro/2026"


def test_xlsx_without_tables_has_no_planned_tables(tmp_path):
    planned = plan_one(tmp_path, xlsx_output())

    assert planned.tables == ()


@pytest.mark.parametrize(
    "invalid_result",
    [
        StructuredResult(message=123),
        StructuredResult(
            message="Done",
            outputs=[
                OutputRequest(
                    format="pdf",
                    filename="report.pdf",
                    tables=[ResultTable(name="Ignored")],
                )
            ],
        ),
        StructuredResult(
            message="Done",
            outputs=[
                OutputRequest(
                    format="xlsx",
                    filename="data.xlsx",
                    tables=[
                        ResultTable(
                            name="Data",
                            headers=["A", "B"],
                            rows=[["one"]],
                        )
                    ],
                )
            ],
        ),
    ],
    ids=["invalid-result", "pdf-tables", "irregular-row"],
)
def test_validation_errors_are_raised_before_planning_touches_filesystem(
    invalid_result,
    tmp_path,
):
    output_dir = tmp_path / "must-not-exist"

    with pytest.raises(OutputValidationError):
        plan_structured_outputs(invalid_result, output_dir, overwrite=False)

    assert not output_dir.exists()


def test_successful_planning_does_not_create_output_or_directory(tmp_path):
    output_dir = tmp_path / "not-created"

    plan = plan_structured_outputs(
        make_result(make_output(filename="planned.txt")),
        output_dir,
    )

    assert plan.outputs[0].path == output_dir / "planned.txt"
    assert not output_dir.exists()
    assert not plan.outputs[0].path.exists()
