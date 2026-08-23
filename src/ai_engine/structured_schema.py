from copy import deepcopy


_NULLABLE_STRING_SCHEMA = {
    "anyOf": [
        {"type": "string"},
        {"type": "null"},
    ]
}

_RESULT_TABLE_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "name": {"type": "string"},
        "headers": {
            "type": "array",
            "items": {"type": "string"},
        },
        "rows": {
            "type": "array",
            "items": {
                "type": "array",
                "items": {"type": "string"},
            },
        },
    },
    "required": ["name", "headers", "rows"],
}

_OUTPUT_REQUEST_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "format": {
            "type": "string",
            "enum": ["txt", "md", "docx", "pdf", "xlsx"],
        },
        "filename": {"type": "string"},
        "title": _NULLABLE_STRING_SCHEMA,
        "content": _NULLABLE_STRING_SCHEMA,
        "tables": {
            "type": "array",
            "items": _RESULT_TABLE_SCHEMA,
        },
    },
    "required": ["format", "filename", "title", "content", "tables"],
}

_STRUCTURED_RESULT_JSON_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "message": {"type": "string"},
        "outputs": {
            "type": "array",
            "items": _OUTPUT_REQUEST_SCHEMA,
        },
    },
    "required": ["message", "outputs"],
}


def get_structured_result_json_schema() -> dict:
    """Return an independent copy of the canonical StructuredResult schema."""

    return deepcopy(_STRUCTURED_RESULT_JSON_SCHEMA)
