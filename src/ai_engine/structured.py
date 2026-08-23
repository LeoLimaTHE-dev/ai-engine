import json

from .results import (
    OutputRequest,
    ResultTable,
    StructuredResult,
)
from .structured_errors import StructuredParseError
from .structured_validation import validate_structured_result

RAW_PREVIEW_LIMIT = 200


def parse_structured_result(
    raw_response: str,
    *,
    expect_outputs: bool = False,
) -> StructuredResult:
    """
    Converts a JSON response produced by the AI
    into StructuredResult.

    If the response is not valid structured JSON,
    it falls back to a normal text-only result.
    """

    if expect_outputs and not isinstance(raw_response, str):
        preview = repr(raw_response)[:RAW_PREVIEW_LIMIT]
        raise StructuredParseError(
            "structured output response must be a string",
            details={
                "raw_preview": preview,
                "raw_truncated": len(repr(raw_response)) > RAW_PREVIEW_LIMIT,
            },
        )

    text = raw_response.strip()

    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        if expect_outputs:
            raise StructuredParseError(
                "expected structured output containing valid JSON",
                details=_raw_response_details(raw_response),
            ) from exc

        return StructuredResult(message=text)

    if not isinstance(data, dict):
        if expect_outputs:
            raise StructuredParseError(
                "structured output root must be a JSON object",
                details=_raw_response_details(raw_response),
            )

        return StructuredResult(message=text)

    if expect_outputs:
        try:
            result = _build_structured_result(data)
        except Exception as exc:
            raise StructuredParseError(
                "could not construct the structured output contract",
                details=_raw_response_details(raw_response),
            ) from exc

        return validate_structured_result(result)

    return _build_structured_result(data)


def _raw_response_details(raw_response: str) -> dict[str, object]:
    return {
        "raw_preview": raw_response[:RAW_PREVIEW_LIMIT],
        "raw_truncated": len(raw_response) > RAW_PREVIEW_LIMIT,
    }


def _build_structured_result(
    data: dict,
) -> StructuredResult:
    message = str(
        data.get(
            "message",
            "",
        )
    )

    outputs_data = data.get(
        "outputs",
        [],
    )

    outputs: list[OutputRequest] = []

    if isinstance(outputs_data, list):
        for output_data in outputs_data:
            if not isinstance(
                output_data,
                dict,
            ):
                continue

            tables: list[ResultTable] = []

            raw_tables = output_data.get(
                "tables",
                [],
            )

            if isinstance(raw_tables, list):
                for table_data in raw_tables:
                    if not isinstance(
                        table_data,
                        dict,
                    ):
                        continue

                    tables.append(
                        ResultTable(
                            name=str(
                                table_data.get(
                                    "name",
                                    "Table",
                                )
                            ),
                            headers=[
                                str(value)
                                for value in table_data.get(
                                    "headers",
                                    [],
                                )
                            ],
                            rows=[
                                [str(cell) for cell in row]
                                for row in table_data.get(
                                    "rows",
                                    [],
                                )
                                if isinstance(
                                    row,
                                    list,
                                )
                            ],
                        )
                    )

            outputs.append(
                OutputRequest(
                    format=str(
                        output_data.get(
                            "format",
                            "",
                        )
                    ).lower(),
                    filename=str(
                        output_data.get(
                            "filename",
                            "",
                        )
                    ),
                    title=output_data.get("title"),
                    content=output_data.get("content"),
                    tables=tables,
                )
            )

    return StructuredResult(
        message=message,
        outputs=outputs,
    )
