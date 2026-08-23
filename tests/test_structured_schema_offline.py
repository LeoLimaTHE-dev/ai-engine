import ast
from dataclasses import fields
import json
from pathlib import Path
import re

import pytest

from ai_engine.actions_prompt import STRUCTURED_OUTPUT_INSTRUCTIONS
from ai_engine.results import OutputRequest, ResultTable, StructuredResult
from ai_engine.structured_errors import OutputValidationError
from ai_engine.structured_schema import get_structured_result_json_schema
from ai_engine.structured_validation import validate_structured_result


ROOT_FIELDS = {"message", "outputs"}
OUTPUT_FIELDS = {"format", "filename", "title", "content", "tables"}
TABLE_FIELDS = {"name", "headers", "rows"}
FORMATS = {"txt", "md", "docx", "pdf", "xlsx"}
NULLABLE_STRING = {"anyOf": [{"type": "string"}, {"type": "null"}]}


@pytest.fixture
def schema():
    return get_structured_result_json_schema()


@pytest.fixture
def output_schema(schema):
    return schema["properties"]["outputs"]["items"]


@pytest.fixture
def table_schema(output_schema):
    return output_schema["properties"]["tables"]["items"]


def test_structured_result_schema_shape(schema):
    assert schema["type"] == "object"
    assert schema["additionalProperties"] is False
    assert set(schema["required"]) == ROOT_FIELDS
    assert set(schema["properties"]) == ROOT_FIELDS
    assert schema["properties"]["message"] == {"type": "string"}
    assert schema["properties"]["outputs"]["type"] == "array"


def test_output_request_schema_shape(output_schema):
    assert output_schema["type"] == "object"
    assert output_schema["additionalProperties"] is False
    assert set(output_schema["required"]) == OUTPUT_FIELDS
    assert set(output_schema["properties"]) == OUTPUT_FIELDS
    assert output_schema["properties"]["format"]["type"] == "string"
    assert set(output_schema["properties"]["format"]["enum"]) == FORMATS
    assert output_schema["properties"]["filename"] == {"type": "string"}
    assert output_schema["properties"]["title"] == NULLABLE_STRING
    assert output_schema["properties"]["content"] == NULLABLE_STRING
    assert output_schema["properties"]["tables"]["type"] == "array"


def test_result_table_schema_shape(table_schema):
    assert table_schema["type"] == "object"
    assert table_schema["additionalProperties"] is False
    assert set(table_schema["required"]) == TABLE_FIELDS
    assert set(table_schema["properties"]) == TABLE_FIELDS
    assert table_schema["properties"]["name"] == {"type": "string"}
    assert table_schema["properties"]["headers"] == {
        "type": "array",
        "items": {"type": "string"},
    }
    assert table_schema["properties"]["rows"] == {
        "type": "array",
        "items": {
            "type": "array",
            "items": {"type": "string"},
        },
    }


def test_schema_getter_returns_deeply_independent_copies():
    first = get_structured_result_json_schema()
    second = get_structured_result_json_schema()

    assert first == second
    assert first is not second

    first["properties"]["outputs"]["items"]["properties"]["format"][
        "enum"
    ].append("csv")

    assert first != second
    assert second["properties"]["outputs"]["items"]["properties"]["format"][
        "enum"
    ] == ["txt", "md", "docx", "pdf", "xlsx"]


def test_schema_is_json_serializable(schema):
    assert json.loads(json.dumps(schema)) == schema


def test_schema_fields_match_public_dataclass_fields(schema, output_schema, table_schema):
    assert set(schema["properties"]) == {field.name for field in fields(StructuredResult)}
    assert set(output_schema["properties"]) == {
        field.name for field in fields(OutputRequest)
    }
    assert set(table_schema["properties"]) == {field.name for field in fields(ResultTable)}


@pytest.mark.parametrize("format_name", sorted(FORMATS))
def test_every_schema_format_is_accepted_by_local_validation(format_name):
    result = StructuredResult(
        message="Done",
        outputs=[OutputRequest(format=format_name, filename=f"file.{format_name}")],
    )

    assert validate_structured_result(result) is result


def test_validator_rejected_format_is_absent_from_schema(output_schema):
    result = StructuredResult(
        message="Done",
        outputs=[OutputRequest(format="csv", filename="file.csv")],
    )

    with pytest.raises(OutputValidationError):
        validate_structured_result(result)

    assert "csv" not in output_schema["properties"]["format"]["enum"]


@pytest.mark.parametrize(("title", "content"), [(None, None), ("Title", "Body")])
def test_nullable_text_contract_matches_local_validation(title, content):
    result = StructuredResult(
        message="Done",
        outputs=[
            OutputRequest(
                format="txt",
                filename="file.txt",
                title=title,
                content=content,
            )
        ],
    )

    assert validate_structured_result(result) is result


def test_message_and_table_cell_string_contract_matches_local_validation():
    valid = StructuredResult(
        message="Done",
        outputs=[
            OutputRequest(
                format="xlsx",
                filename="file.xlsx",
                tables=[ResultTable(name="Data", rows=[["value"]])],
            )
        ],
    )
    assert validate_structured_result(valid) is valid

    invalid_message = StructuredResult(message=None)
    with pytest.raises(OutputValidationError):
        validate_structured_result(invalid_message)

    invalid_cell = StructuredResult(
        message="Done",
        outputs=[
            OutputRequest(
                format="xlsx",
                filename="file.xlsx",
                tables=[ResultTable(name="Data", rows=[[1]])],
            )
        ],
    )
    with pytest.raises(OutputValidationError):
        validate_structured_result(invalid_cell)


def test_schema_contract_matches_actions_prompt(schema, output_schema, table_schema):
    formats_section = STRUCTURED_OUTPUT_INSTRUCTIONS.split(
        "The only supported output formats are:", 1
    )[1].split("Format rules:", 1)[0]
    prompt_formats = set(re.findall(r'^- "([^"]+)"$', formats_section, re.MULTILINE))
    type_section = STRUCTURED_OUTPUT_INSTRUCTIONS.split("Field types:", 1)[1].split(
        "The only supported output formats are:", 1
    )[0]
    prompt_fields = set(re.findall(r'^- (?:table )?"([^"]+)":', type_section, re.MULTILINE))

    assert prompt_formats == set(output_schema["properties"]["format"]["enum"])
    assert prompt_fields == (
        set(schema["properties"])
        | set(output_schema["properties"])
        | set(table_schema["properties"])
    )


def test_all_provider_adapters_use_the_canonical_structured_schema():
    providers_dir = Path(__file__).resolve().parents[1] / "src" / "ai_engine" / "providers"

    for provider_name in (
        "openai_provider.py",
        "anthropic_provider.py",
        "gemini_provider.py",
    ):
        provider_path = providers_dir / provider_name
        source = provider_path.read_text(encoding="utf-8")
        ast.parse(source)
        assert "structured_schema" in source
        assert "get_structured_result_json_schema" in source
