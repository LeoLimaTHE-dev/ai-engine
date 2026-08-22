import json

from .results import (
    OutputRequest,
    ResultTable,
    StructuredResult,
)


def parse_structured_result(
    raw_response: str,
) -> StructuredResult:
    """
    Converts a JSON response produced by the AI
    into StructuredResult.

    If the response is not valid structured JSON,
    it falls back to a normal text-only result.
    """

    text = raw_response.strip()

    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        return StructuredResult(message=text)

    if not isinstance(data, dict):
        return StructuredResult(message=text)

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
