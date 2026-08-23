import base64
import math
import os
from collections.abc import Callable
from typing import TypeVar

from google import genai
from google.genai import errors as genai_errors
from google.genai import types as genai_types
from google.genai._gaos.lib.compat_errors import (
    APIConnectionError as InteractionsAPIConnectionError,
    APIStatusError as InteractionsAPIStatusError,
    APITimeoutError as InteractionsAPITimeoutError,
    AuthenticationError as InteractionsAuthenticationError,
    BadRequestError as InteractionsBadRequestError,
    GeminiNextGenAPIClientError as InteractionsError,
    NotFoundError as InteractionsNotFoundError,
    PermissionDeniedError as InteractionsPermissionDeniedError,
    RateLimitError as InteractionsRateLimitError,
)

from ai_engine.config import get_provider_timeout_seconds
from ai_engine.images import normalize_image
from ai_engine.models import DocumentContent
from ai_engine.provider_capabilities import get_configured_document_model
from ai_engine.structured_schema import get_structured_result_json_schema
from ai_engine.usage import (
    UsageRecord,
    log_usage,
)

from .errors import (
    ProviderConnectionError,
    ProviderError,
    ProviderRateLimitError,
    ProviderRequestError,
    ProviderTimeoutError,
    parse_retry_after_seconds,
)


ResultT = TypeVar("ResultT")
GeminiSDKError = InteractionsError | genai_errors.APIError


def _gemini_http_options() -> genai_types.HttpOptions:
    timeout_milliseconds = math.ceil(get_provider_timeout_seconds() * 1000)

    return genai_types.HttpOptions(
        timeout=timeout_milliseconds,
    )


def _structured_error_code(exc: GeminiSDKError, details: object) -> str | None:
    status = getattr(exc, "status", None)

    if status is not None:
        return str(status)

    if isinstance(details, dict):
        error_details = details.get("error", details)

        if isinstance(error_details, dict):
            code = error_details.get("status") or error_details.get("code")

            if code is not None:
                return str(code)

    code = getattr(exc, "code", None)

    if code is not None:
        return str(code)

    return None


def _gemini_error_metadata(exc: GeminiSDKError) -> dict[str, object]:
    response = getattr(exc, "response", None)
    headers = getattr(response, "headers", None)

    retry_after_seconds = None

    if headers is not None:
        retry_after_seconds = parse_retry_after_seconds(
            retry_after=headers.get("retry-after"),
            retry_after_ms=headers.get("retry-after-ms"),
        )

    details = getattr(exc, "body", None)

    if details is None:
        details = getattr(exc, "details", None)

    status_code = getattr(exc, "status_code", None)

    if status_code is None:
        status_code = getattr(exc, "code", None)

    return {
        "provider": "gemini",
        "message": (
            getattr(exc, "message", None) or str(exc) or "Gemini request failed."
        ),
        "status_code": status_code if isinstance(status_code, int) else None,
        "error_code": _structured_error_code(exc, details),
        "retry_after_seconds": retry_after_seconds,
        "details": details,
    }


def _normalize_gemini_error(exc: GeminiSDKError) -> ProviderError:
    metadata = _gemini_error_metadata(exc)
    status_code = metadata["status_code"]

    if isinstance(exc, InteractionsRateLimitError) or status_code == 429:
        retry_after_seconds = metadata["retry_after_seconds"]

        return ProviderRateLimitError(
            **metadata,
            retryable=(
                isinstance(retry_after_seconds, float) and retry_after_seconds > 0
            ),
        )

    if isinstance(exc, InteractionsAPITimeoutError):
        return ProviderTimeoutError(
            **metadata,
            retryable=True,
        )

    if isinstance(exc, InteractionsAPIConnectionError):
        return ProviderConnectionError(
            **metadata,
            retryable=True,
        )

    if isinstance(status_code, int) and status_code >= 500:
        return ProviderError(
            **metadata,
            retryable=True,
        )

    if isinstance(
        exc,
        (
            InteractionsAuthenticationError,
            InteractionsBadRequestError,
            InteractionsNotFoundError,
            InteractionsPermissionDeniedError,
            InteractionsAPIStatusError,
            genai_errors.ClientError,
        ),
    ):
        return ProviderRequestError(
            **metadata,
            retryable=False,
        )

    return ProviderError(
        **metadata,
        retryable=False,
    )


def _call_gemini(operation: Callable[[], ResultT]) -> ResultT:
    try:
        return operation()
    except (InteractionsError, genai_errors.APIError) as exc:
        raise _normalize_gemini_error(exc) from exc


def _structured_response_format() -> dict[str, object]:
    return {
        "type": "text",
        "mime_type": "application/json",
        "schema": get_structured_result_json_schema(),
    }


def _ensure_native_structured_interaction(interaction: object) -> None:
    status = getattr(interaction, "status", None)

    if status is not None and status != "completed":
        raise ProviderRequestError(
            provider="gemini",
            message=f"Gemini structured interaction has status {status!r}.",
            error_code=f"interaction_{status}",
            retryable=False,
            details=getattr(interaction, "errors", None),
        )


def ask_gemini(prompt: str, *, native_structured: bool = False) -> str:
    client = genai.Client(http_options=_gemini_http_options())

    model = os.getenv("GEMINI_MODEL", "gemini-3.6-flash")

    request = {
        "model": model,
        "input": prompt,
    }

    if native_structured:
        request["response_format"] = _structured_response_format()

    interaction = _call_gemini(lambda: client.interactions.create(**request))

    usage = interaction.usage

    if usage is not None:
        log_usage(
            UsageRecord(
                provider="gemini",
                model=model,
                input_tokens=(usage.total_input_tokens or 0),
                output_tokens=(usage.total_output_tokens or 0),
                thought_tokens=(usage.total_thought_tokens or 0),
                cached_tokens=(usage.total_cached_tokens or 0),
                total_tokens=(usage.total_tokens or 0),
            )
        )

    if native_structured:
        _ensure_native_structured_interaction(interaction)

    return interaction.output_text


def ask_gemini_document(
    document: DocumentContent,
    prompt: str,
    *,
    native_structured: bool = False,
) -> str:
    client = genai.Client(http_options=_gemini_http_options())

    model = get_configured_document_model("gemini")
    assert model is not None

    content = document.to_text()

    full_prompt = f"""
{prompt}

DOCUMENT CONTENT:

{content}
""".strip()

    inputs = [
        {
            "type": "text",
            "text": full_prompt,
        }
    ]

    for image in document.images:
        image = normalize_image(image)

        if not image.media_type:
            continue

        encoded_image = base64.b64encode(image.data).decode("utf-8")

        inputs.append(
            {
                "type": "image",
                "data": encoded_image,
                "mime_type": image.media_type,
            }
        )

    request = {
        "model": model,
        "input": inputs,
    }

    if native_structured:
        request["response_format"] = _structured_response_format()

    interaction = _call_gemini(lambda: client.interactions.create(**request))

    usage = interaction.usage

    if usage is not None:
        log_usage(
            UsageRecord(
                provider="gemini",
                model=model,
                input_tokens=(usage.total_input_tokens or 0),
                output_tokens=(usage.total_output_tokens or 0),
                thought_tokens=(usage.total_thought_tokens or 0),
                cached_tokens=(usage.total_cached_tokens or 0),
                total_tokens=(usage.total_tokens or 0),
            )
        )

    if native_structured:
        _ensure_native_structured_interaction(interaction)

    return interaction.output_text
