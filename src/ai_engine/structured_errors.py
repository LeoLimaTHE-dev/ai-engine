class StructuredOutputError(Exception):
    def __init__(
        self,
        message: str,
        *,
        field_path: str | None = None,
        details: object | None = None,
    ) -> None:
        self.message = message
        self.field_path = field_path
        self.details = details

        super().__init__(message)

    def __str__(self) -> str:
        if self.field_path:
            return f"{self.field_path}: {self.message}"

        return self.message


class StructuredParseError(StructuredOutputError):
    pass


class OutputValidationError(StructuredOutputError):
    pass


class OutputExecutionError(StructuredOutputError):
    pass
