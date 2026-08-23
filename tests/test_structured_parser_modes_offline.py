import ast
import json
from pathlib import Path

import pytest

from ai_engine.results import OutputRequest, ResultTable, StructuredResult
from ai_engine.structured import RAW_PREVIEW_LIMIT, parse_structured_result
from ai_engine.structured_errors import OutputValidationError, StructuredParseError


@pytest.mark.parametrize(
    "raw_response",
    [
        "Normal text",
        "{invalid}",
        '```json\n{"message": "fenced"}\n```',
        "[1, 2]",
    ],
    ids=["text", "invalid-json", "fenced", "array"],
)
def test_default_mode_is_equivalent_to_explicit_legacy_mode(raw_response):
    assert parse_structured_result(raw_response) == parse_structured_result(
        raw_response,
        expect_outputs=False,
    )


@pytest.mark.parametrize(
    "raw_response",
    [
        "Normal text",
        "{invalid}",
        '{"message": "partial"',
        '```json\n{"message": "fenced"}\n```',
        'prefix {"message": "value"}',
        '{"message": "value"} suffix',
        "",
    ],
    ids=["text", "invalid", "partial", "fenced", "prefix", "suffix", "empty"],
)
def test_strong_mode_rejects_non_json_text(raw_response):
    with pytest.raises(StructuredParseError, match="expected structured output"):
        parse_structured_result(raw_response, expect_outputs=True)


@pytest.mark.parametrize(
    "raw_response",
    ["[1, 2]", '"root string"', "null"],
    ids=["array", "string", "null"],
)
def test_strong_mode_rejects_non_object_json_root(raw_response):
    with pytest.raises(StructuredParseError, match="root must be a JSON object") as captured:
        parse_structured_result(raw_response, expect_outputs=True)

    assert captured.value.__cause__ is None


def test_json_decode_error_is_preserved_as_parse_error_cause():
    with pytest.raises(StructuredParseError) as captured:
        parse_structured_result("{invalid}", expect_outputs=True)

    assert isinstance(captured.value.__cause__, json.JSONDecodeError)


def test_parse_error_uses_limited_raw_preview_without_echoing_large_response():
    raw_response = "x" * (RAW_PREVIEW_LIMIT + 100)

    with pytest.raises(StructuredParseError) as captured:
        parse_structured_result(raw_response, expect_outputs=True)

    assert captured.value.details == {
        "raw_preview": "x" * RAW_PREVIEW_LIMIT,
        "raw_truncated": True,
    }
    assert raw_response not in str(captured.value)


@pytest.mark.parametrize("raw_response", [None, 123])
def test_strong_mode_rejects_non_string_raw_response(raw_response):
    with pytest.raises(StructuredParseError, match="must be a string"):
        parse_structured_result(raw_response, expect_outputs=True)


def test_minimal_json_object_is_valid_in_strong_mode():
    result = parse_structured_result('{"message": "Done"}', expect_outputs=True)

    assert result == StructuredResult(message="Done")


def test_empty_json_object_remains_valid_in_strong_mode():
    assert parse_structured_result("{}", expect_outputs=True) == StructuredResult(
        message="",
        outputs=[],
    )


def test_empty_outputs_are_valid_in_strong_mode():
    result = parse_structured_result(
        '{"message": "Could not create", "outputs": []}',
        expect_outputs=True,
    )

    assert result == StructuredResult(message="Could not create", outputs=[])


def test_valid_txt_output_is_built_and_validated_in_strong_mode():
    raw_response = json.dumps(
        {
            "message": "Created",
            "outputs": [
                {
                    "format": "TXT",
                    "filename": "result.txt",
                    "content": "Body",
                }
            ],
        }
    )

    result = parse_structured_result(raw_response, expect_outputs=True)

    assert result.outputs == [
        OutputRequest(format="txt", filename="result.txt", content="Body")
    ]


def test_valid_xlsx_table_is_built_and_validated_in_strong_mode():
    raw_response = json.dumps(
        {
            "outputs": [
                {
                    "format": "xlsx",
                    "filename": "data.xlsx",
                    "tables": [
                        {
                            "name": "Data",
                            "headers": ["A", "B"],
                            "rows": [["1", "2"]],
                        }
                    ],
                }
            ]
        }
    )

    result = parse_structured_result(raw_response, expect_outputs=True)

    assert result.outputs[0].tables == [
        ResultTable(name="Data", headers=["A", "B"], rows=[["1", "2"]])
    ]


@pytest.mark.parametrize(
    ("output_data", "expected_path"),
    [
        ({"format": "csv", "filename": "file.csv"}, "outputs[0].format"),
        ({"format": "txt", "filename": ""}, "outputs[0].filename"),
        (
            {"format": "txt", "filename": "file.txt", "content": 123},
            "outputs[0].content",
        ),
        (
            {
                "format": "pdf",
                "filename": "file.pdf",
                "tables": [{"name": "Ignored"}],
            },
            "outputs[0].tables",
        ),
        (
            {
                "format": "xlsx",
                "filename": "file.xlsx",
                "tables": [
                    {"name": "Data", "headers": ["A", "B"], "rows": [["one"]]}
                ],
            },
            "outputs[0].tables[0].rows[0]",
        ),
    ],
    ids=["format", "filename", "content", "pdf-tables", "irregular-table"],
)
def test_strong_mode_preserves_output_validation_errors(output_data, expected_path):
    raw_response = json.dumps({"message": "Done", "outputs": [output_data]})

    with pytest.raises(OutputValidationError) as captured:
        parse_structured_result(raw_response, expect_outputs=True)

    assert captured.value.field_path == expected_path
    assert not isinstance(captured.value, StructuredParseError)


@pytest.mark.parametrize("field", ["headers", "rows"])
def test_null_table_collection_becomes_parse_error_with_original_cause(field):
    raw_response = json.dumps(
        {
            "outputs": [
                {
                    "format": "xlsx",
                    "filename": "data.xlsx",
                    "tables": [{field: None}],
                }
            ]
        }
    )

    with pytest.raises(StructuredParseError, match="could not construct") as captured:
        parse_structured_result(raw_response, expect_outputs=True)

    assert isinstance(captured.value.__cause__, TypeError)


@pytest.mark.parametrize("field", ["headers", "rows"])
def test_legacy_mode_still_exposes_type_error_for_null_table_collection(field):
    raw_response = json.dumps(
        {
            "outputs": [
                {
                    "format": "xlsx",
                    "filename": "data.xlsx",
                    "tables": [{field: None}],
                }
            ]
        }
    )

    with pytest.raises(TypeError):
        parse_structured_result(raw_response)


def test_only_application_workflow_and_chat_control_expect_outputs():
    project_root = Path(__file__).resolve().parents[1]
    source_paths = [
        *project_root.joinpath("src", "ai_engine").rglob("*.py"),
        *project_root.joinpath("application").rglob("*.py"),
    ]

    consumers = set()

    for source_path in source_paths:
        if source_path.name == "structured.py":
            continue

        tree = ast.parse(source_path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            for keyword in node.keywords:
                if keyword.arg == "expect_outputs":
                    consumers.add(source_path.name)

    assert consumers == {"ia_interativa.py", "chat.py", "workflow.py"}
