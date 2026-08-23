import json

from ai_engine.actions_prompt import STRUCTURED_OUTPUT_INSTRUCTIONS


PROMPT = STRUCTURED_OUTPUT_INSTRUCTIONS
LOWER_PROMPT = PROMPT.lower()


def section(start, end):
    return PROMPT.split(start, 1)[1].split(end, 1)[0]


def json_example(start, end=None):
    fragment = PROMPT.split(start, 1)[1]
    if end is not None:
        fragment = fragment.split(end, 1)[0]
    return json.loads(fragment[fragment.index("{") : fragment.rindex("}") + 1])


def test_prompt_distinguishes_normal_text_from_explicit_file_contract():
    assert "does NOT request files" in PROMPT
    assert "answer normally in plain text" in PROMPT
    assert "structured output is expected" in PROMPT


def test_prompt_announces_exactly_the_supported_format_values():
    formats = section(
        "The only supported output formats are:",
        "Format rules:",
    )

    assert formats.count('\n- "') == 5
    for value in ("txt", "md", "docx", "pdf", "xlsx"):
        assert f'- "{value}"' in formats
    assert "csv" not in LOWER_PROMPT
    assert '"format": "markdown"' not in LOWER_PROMPT
    assert '"markdown" is not a supported format' in LOWER_PROMPT


def test_prompt_requires_pure_json_without_recovery_wrappers():
    assert "exactly one valid JSON object and nothing else" in PROMPT
    assert "Do not use Markdown\nfences such as ```json" in PROMPT
    assert "introductory\ntext, or text after the JSON" in PROMPT
    assert "trailing commas" in PROMPT
    assert "double quotes" in PROMPT
    assert "JSON null" in PROMPT


def test_prompt_documents_all_field_types_and_string_only_cells():
    types = section("Field types:", "The only supported output formats are:")

    for field in (
        '"message": string',
        '"outputs": array',
        '"format": string',
        '"filename": string',
        '"title": string or null',
        '"content": string or null',
        '"tables": array',
        '"name": string',
        '"headers": array of strings',
        '"rows": array of arrays of strings',
    ):
        assert field in types
    assert "Every cell must be a string" in types
    assert "numbers, objects, or null as cells" in types


def test_txt_contract_is_textual_and_has_no_tables():
    rules = section("Format rules:", "Filename rules:")

    assert "TXT is simple text" in rules
    assert 'Put it in "content"' in rules
    assert 'use "tables": []' in rules
    assert "ending in .txt" in rules


def test_md_contract_uses_md_and_does_not_offer_markdown_alias():
    rules = section("Format rules:", "Filename rules:")

    assert 'Markdown uses "format": "md"' in rules
    assert 'textual Markdown in "content"' in rules
    assert 'The value "markdown" is not a supported format' in rules
    assert "Prefer .md" in rules


def test_docx_contract_is_limited_to_title_and_text_content():
    rules = section("Format rules:", "Filename rules:")
    docx_rule = rules.split("- DOCX", 1)[1].split("- PDF", 1)[0]

    assert '"title" and textual "content"' in docx_rule
    assert "does not render Markdown, structured lists, images, or tables" in docx_rule
    assert 'Always use "tables": []' in docx_rule


def test_pdf_contract_is_limited_to_title_and_text_content():
    rules = section("Format rules:", "Filename rules:")
    pdf_rule = rules.split("- PDF", 1)[1].split("- XLSX", 1)[0]

    assert '"title" and textual "content"' in pdf_rule
    assert "does not render Markdown, images, or tables" in pdf_rule
    assert 'Always use\n  "tables": []' in pdf_rule


def test_xlsx_contract_describes_linear_and_tabular_modes():
    rules = section("Format rules:", "Filename rules:")
    xlsx_rule = rules.split("- XLSX", 1)[1]

    assert "Linear mode" in xlsx_rule
    assert 'textual "content" and "tables": []' in xlsx_rule
    assert "written linearly in one worksheet" in xlsx_rule
    assert "Tabular mode" in xlsx_rule
    assert 'one or more tables in "tables"' in xlsx_rule
    assert "Each table becomes a\n     worksheet" in xlsx_rule


def test_xlsx_rows_and_headers_have_consistent_string_width_contract():
    rules = section("Format rules:", "Filename rules:")
    xlsx_rule = rules.split("- XLSX", 1)[1]

    assert "Headers must be strings" in xlsx_rule
    assert "rows must contain only strings" in xlsx_rule
    assert "all rows must have consistent widths" in xlsx_rule
    assert "exactly as many cells as the\n     headers" in xlsx_rule


def test_filename_policy_requests_simple_safe_names_not_paths():
    rules = section("Filename rules:", '"message" should')

    assert "simple, safe filename, never a path" in rules
    assert "absolute paths" in rules
    assert "../" in rules
    assert "subdirectories" in rules
    for reserved in ("CON", "PRN", "AUX", "NUL", "COM1", "LPT1"):
        assert reserved in rules


def test_filename_extensions_must_match_formats_and_be_distinct():
    rules = section("Filename rules:", '"message" should')

    assert "Match the extension to the format" in rules
    for extension in (".txt", ".md", ".docx", ".pdf", ".xlsx"):
        assert extension in rules
    assert "Every output must use a distinct filename" in rules


def test_message_describes_preparation_without_claiming_completed_write():
    message_rule = section('"message" should', "Multiple independent outputs")

    assert "prepared for generation" in message_rule
    assert "Do not claim that a\nfile has already been created" in message_rule


def test_multiple_output_example_is_valid_and_independent():
    example = json_example("Multiple independent outputs", "DOCX textual example:")

    assert len(example["outputs"]) == 2
    assert [output["format"] for output in example["outputs"]] == ["docx", "xlsx"]
    assert len({output["filename"] for output in example["outputs"]}) == 2
    assert "created" not in example["message"].lower()


def test_docx_example_matches_runtime_contract():
    example = json_example("DOCX textual example:", "XLSX tabular example:")
    output = example["outputs"][0]

    assert output == {
        "format": "docx",
        "filename": "report.docx",
        "title": "Report",
        "content": "Plain report text",
        "tables": [],
    }


def test_xlsx_tabular_example_matches_runtime_contract():
    example = json_example(
        "XLSX tabular example:",
        "If no valid output can be prepared",
    )
    output = example["outputs"][0]
    table = output["tables"][0]

    assert output["format"] == "xlsx"
    assert output["title"] is None
    assert output["content"] is None
    assert table["headers"] == ["Column A", "Column B"]
    assert table["rows"] == [["value 1", "value 2"]]


def test_empty_outputs_are_explicitly_allowed():
    example = json_example("If no valid output can be prepared")

    assert example["outputs"] == []
    assert isinstance(example["message"], str)
