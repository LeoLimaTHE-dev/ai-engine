import pytest

from ai_engine.results import OutputRequest, ResultTable, StructuredResult
from ai_engine.structured_errors import (
    OutputExecutionError,
    OutputValidationError,
    StructuredOutputError,
    StructuredParseError,
)
from ai_engine.structured_validation import validate_structured_result


def valid_output(**overrides):
    values = {
        "format": "txt",
        "filename": "result.txt",
        "content": "content",
    }
    values.update(overrides)
    return OutputRequest(**values)


def valid_result(**output_overrides):
    return StructuredResult(message="Done", outputs=[valid_output(**output_overrides)])


@pytest.mark.parametrize(
    "error_type",
    [StructuredParseError, OutputValidationError, OutputExecutionError],
)
def test_structured_error_subclasses_share_common_base(error_type):
    error = error_type("failure")

    assert isinstance(error, StructuredOutputError)


def test_structured_error_preserves_metadata_and_formats_field_path():
    details = {"expected": "str"}
    error = OutputValidationError(
        "expected str",
        field_path="outputs[1].filename",
        details=details,
    )

    assert error.message == "expected str"
    assert error.field_path == "outputs[1].filename"
    assert error.details is details
    assert str(error) == "outputs[1].filename: expected str"


def test_structured_error_without_field_path_uses_plain_message():
    assert str(StructuredParseError("invalid JSON")) == "invalid JSON"


def test_empty_structured_result_is_valid():
    result = StructuredResult(message="", outputs=[])

    assert validate_structured_result(result) is result


def test_valid_result_returns_same_object():
    result = valid_result()

    assert validate_structured_result(result) is result


def test_non_structured_result_is_rejected():
    with pytest.raises(OutputValidationError, match=r"result: expected StructuredResult"):
        validate_structured_result({"message": "Done"})


def test_non_string_message_is_rejected():
    result = StructuredResult(message=123)

    with pytest.raises(OutputValidationError, match=r"message: expected str"):
        validate_structured_result(result)


def test_non_list_outputs_are_rejected():
    result = StructuredResult(message="Done", outputs="not-a-list")

    with pytest.raises(OutputValidationError, match=r"outputs: expected list"):
        validate_structured_result(result)


def test_non_output_request_item_is_rejected_with_index():
    result = StructuredResult(message="Done", outputs=["not-an-output"])

    with pytest.raises(OutputValidationError, match=r"outputs\[0\]: expected OutputRequest"):
        validate_structured_result(result)


@pytest.mark.parametrize(
    "format_name",
    ["txt", "md", "docx", "pdf", "xlsx", "TXT", ".txt", "PDF", ".xlsx"],
)
def test_supported_format_variants_are_accepted_without_mutation(format_name):
    result = valid_result(format=format_name)

    assert validate_structured_result(result) is result
    assert result.outputs[0].format == format_name


@pytest.mark.parametrize("format_name", ["markdown", "csv", "", "   ", "none"])
def test_unsupported_or_empty_format_is_rejected(format_name):
    result = valid_result(format=format_name)

    with pytest.raises(OutputValidationError) as captured:
        validate_structured_result(result)

    assert captured.value.field_path == "outputs[0].format"
    assert "unsupported format" in str(captured.value)


def test_non_string_format_is_rejected():
    result = valid_result(format=None)

    with pytest.raises(OutputValidationError) as captured:
        validate_structured_result(result)

    assert captured.value.field_path == "outputs[0].format"


@pytest.mark.parametrize("filename", ["file.txt", "../../file.txt", "CON"])
def test_structurally_valid_filenames_are_accepted_for_future_planning(filename):
    result = valid_result(filename=filename)

    assert validate_structured_result(result) is result
    assert result.outputs[0].filename == filename


@pytest.mark.parametrize("filename", ["", "   ", ".", ".."])
def test_empty_or_dot_filename_is_rejected(filename):
    result = valid_result(filename=filename)

    with pytest.raises(OutputValidationError) as captured:
        validate_structured_result(result)

    assert captured.value.field_path == "outputs[0].filename"


def test_non_string_filename_is_rejected():
    result = valid_result(filename=123)

    with pytest.raises(OutputValidationError) as captured:
        validate_structured_result(result)

    assert captured.value.field_path == "outputs[0].filename"


@pytest.mark.parametrize(("field", "value"), [("title", 123), ("content", 123)])
def test_non_string_optional_text_fields_are_rejected(field, value):
    result = valid_result(**{field: value})

    with pytest.raises(OutputValidationError) as captured:
        validate_structured_result(result)

    assert captured.value.field_path == f"outputs[0].{field}"


@pytest.mark.parametrize(("title", "content"), [(None, None), ("", "")])
def test_none_or_empty_optional_text_fields_are_valid(title, content):
    result = valid_result(title=title, content=content)

    assert validate_structured_result(result) is result


def test_non_list_tables_are_rejected():
    result = valid_result(format="xlsx", filename="data.xlsx", tables="not-a-list")

    with pytest.raises(OutputValidationError) as captured:
        validate_structured_result(result)

    assert captured.value.field_path == "outputs[0].tables"


def test_non_result_table_item_is_rejected_with_index():
    result = valid_result(format="xlsx", filename="data.xlsx", tables=["bad"])

    with pytest.raises(OutputValidationError) as captured:
        validate_structured_result(result)

    assert captured.value.field_path == "outputs[0].tables[0]"


@pytest.mark.parametrize("format_name", ["txt", "md", "docx", "pdf"])
def test_empty_tables_are_valid_for_non_xlsx_formats(format_name):
    result = valid_result(format=format_name, tables=[])

    assert validate_structured_result(result) is result


@pytest.mark.parametrize("format_name", ["txt", "md", "docx", "pdf"])
def test_non_empty_tables_are_rejected_for_formats_that_ignore_them(format_name):
    result = valid_result(format=format_name, tables=[ResultTable(name="Data")])

    with pytest.raises(OutputValidationError) as captured:
        validate_structured_result(result)

    assert captured.value.field_path == "outputs[0].tables"
    assert "not supported" in str(captured.value)


def test_xlsx_linear_content_without_tables_is_valid():
    result = valid_result(
        format="xlsx",
        filename="data.xlsx",
        content="linear",
        tables=[],
    )

    assert validate_structured_result(result) is result


def test_xlsx_tables_with_content_are_still_valid():
    result = valid_result(
        format="xlsx",
        filename="data.xlsx",
        content="currently ignored",
        tables=[ResultTable(name="Data", headers=["A"], rows=[["value"]])],
    )

    assert validate_structured_result(result) is result


def test_empty_table_is_valid():
    result = valid_result(
        format="xlsx",
        filename="data.xlsx",
        tables=[ResultTable(name="")],
    )

    assert validate_structured_result(result) is result


def test_table_with_valid_headers_and_equal_width_rows_is_valid():
    result = valid_result(
        format="xlsx",
        filename="data.xlsx",
        tables=[ResultTable(name="Data", headers=["A", "B"], rows=[["1", "2"]])],
    )

    assert validate_structured_result(result) is result


def test_string_headers_are_rejected():
    result = valid_result(
        format="xlsx",
        filename="data.xlsx",
        tables=[ResultTable(name="Data", headers="AB")],
    )

    with pytest.raises(OutputValidationError) as captured:
        validate_structured_result(result)

    assert captured.value.field_path == "outputs[0].tables[0].headers"


def test_non_string_header_is_rejected_with_index():
    result = valid_result(
        format="xlsx",
        filename="data.xlsx",
        tables=[ResultTable(name="Data", headers=["A", 2])],
    )

    with pytest.raises(OutputValidationError) as captured:
        validate_structured_result(result)

    assert captured.value.field_path == "outputs[0].tables[0].headers[1]"


def test_string_rows_are_rejected():
    result = valid_result(
        format="xlsx",
        filename="data.xlsx",
        tables=[ResultTable(name="Data", rows="not-a-list")],
    )

    with pytest.raises(OutputValidationError) as captured:
        validate_structured_result(result)

    assert captured.value.field_path == "outputs[0].tables[0].rows"


def test_non_list_row_is_rejected_with_index():
    result = valid_result(
        format="xlsx",
        filename="data.xlsx",
        tables=[ResultTable(name="Data", rows=["bad-row"])],
    )

    with pytest.raises(OutputValidationError) as captured:
        validate_structured_result(result)

    assert captured.value.field_path == "outputs[0].tables[0].rows[0]"


def test_non_string_cell_is_rejected_with_full_path():
    result = valid_result(
        format="xlsx",
        filename="data.xlsx",
        tables=[ResultTable(name="Data", rows=[["A", 2]])],
    )

    with pytest.raises(OutputValidationError) as captured:
        validate_structured_result(result)

    assert captured.value.field_path == "outputs[0].tables[0].rows[0][1]"


def test_row_width_must_match_headers():
    result = valid_result(
        format="xlsx",
        filename="data.xlsx",
        tables=[ResultTable(name="Data", headers=["A", "B"], rows=[["only-one"]])],
    )

    with pytest.raises(OutputValidationError) as captured:
        validate_structured_result(result)

    assert captured.value.field_path == "outputs[0].tables[0].rows[0]"
    assert "expected 2 cells, got 1" in str(captured.value)


def test_rows_without_headers_are_valid_when_widths_match():
    result = valid_result(
        format="xlsx",
        filename="data.xlsx",
        tables=[ResultTable(name="Data", rows=[["A", "B"], ["C", "D"]])],
    )

    assert validate_structured_result(result) is result


def test_rows_without_headers_are_rejected_when_widths_differ():
    result = valid_result(
        format="xlsx",
        filename="data.xlsx",
        tables=[ResultTable(name="Data", rows=[["A", "B"], ["C"]])],
    )

    with pytest.raises(OutputValidationError) as captured:
        validate_structured_result(result)

    assert captured.value.field_path == "outputs[0].tables[0].rows[1]"
    assert "expected 2 cells, got 1" in str(captured.value)


def test_non_string_table_name_is_rejected():
    result = valid_result(
        format="xlsx",
        filename="data.xlsx",
        tables=[ResultTable(name=123)],
    )

    with pytest.raises(OutputValidationError) as captured:
        validate_structured_result(result)

    assert captured.value.field_path == "outputs[0].tables[0].name"


def test_validation_does_not_mutate_format_or_filename():
    result = valid_result(format="TXT", filename="  ../../Report.TXT  ")
    original_output = result.outputs[0]

    validated = validate_structured_result(result)

    assert validated is result
    assert validated.outputs[0] is original_output
    assert original_output.format == "TXT"
    assert original_output.filename == "  ../../Report.TXT  "
