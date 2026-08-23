import base64
import os
from collections.abc import Callable
from typing import TypeVar

from anthropic import (
    APIConnectionError,
    APIStatusError,
    APITimeoutError,
    Anthropic,
    AnthropicError,
    AuthenticationError,
    BadRequestError,
    NotFoundError,
    PermissionDeniedError,
    RateLimitError,
    RequestTooLargeError,
)

from ai_engine.config import (
    get_provider_max_retries,
    get_provider_retry_base_delay_seconds,
    get_provider_retry_max_delay_seconds,
    get_provider_timeout_seconds,
)
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
from .retry import retry_provider_call


ResultT = TypeVar("ResultT")


def _anthropic_error_metadata(exc: AnthropicError) -> dict[str, object]:
    response = getattr(exc, "response", None)
    headers = getattr(response, "headers", None)

    retry_after_seconds = None

    if headers is not None:
        retry_after_seconds = parse_retry_after_seconds(
            retry_after=headers.get("retry-after"),
            retry_after_ms=headers.get("retry-after-ms"),
        )

    error_code = getattr(exc, "type", None)

    if error_code is not None:
        error_code = str(error_code)

    return {
        "provider": "anthropic",
        "message": (
            getattr(exc, "message", None)
            or str(exc)
            or "Anthropic request failed."
        ),
        "status_code": getattr(exc, "status_code", None),
        "error_code": error_code,
        "retry_after_seconds": retry_after_seconds,
        "details": getattr(exc, "body", None),
    }


def _normalize_anthropic_error(exc: AnthropicError) -> ProviderError:
    metadata = _anthropic_error_metadata(exc)

    if isinstance(exc, RateLimitError):
        retry_after_seconds = metadata["retry_after_seconds"]

        return ProviderRateLimitError(
            **metadata,
            retryable=(
                isinstance(retry_after_seconds, float) and retry_after_seconds > 0
            ),
        )

    if isinstance(exc, APITimeoutError):
        return ProviderTimeoutError(
            **metadata,
            retryable=True,
        )

    if isinstance(exc, APIConnectionError):
        return ProviderConnectionError(
            **metadata,
            retryable=True,
        )

    status_code = metadata["status_code"]

    if isinstance(status_code, int) and status_code >= 500:
        return ProviderError(
            **metadata,
            retryable=True,
        )

    if isinstance(
        exc,
        (
            AuthenticationError,
            BadRequestError,
            NotFoundError,
            PermissionDeniedError,
            RequestTooLargeError,
            APIStatusError,
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


def _call_anthropic(operation: Callable[[], ResultT]) -> ResultT:
    def call_once() -> ResultT:
        try:
            return operation()
        except AnthropicError as exc:
            raise _normalize_anthropic_error(exc) from exc

    return retry_provider_call(
        call_once,
        max_retries=get_provider_max_retries(),
        base_delay_seconds=get_provider_retry_base_delay_seconds(),
        max_delay_seconds=get_provider_retry_max_delay_seconds(),
    )


def _structured_output_config() -> dict[str, object]:
    return {
        "format": {
            "type": "json_schema",
            "schema": get_structured_result_json_schema(),
        }
    }


def _ensure_native_structured_message(message: object) -> None:
    stop_reason = getattr(message, "stop_reason", None)

    if stop_reason is not None and stop_reason != "end_turn":
        raise ProviderRequestError(
            provider="anthropic",
            message=(
                "Anthropic structured response stopped with "
                f"reason {stop_reason!r}."
            ),
            error_code=f"stop_reason_{stop_reason}",
            retryable=False,
            details={"stop_reason": stop_reason},
        )


def ask_anthropic(prompt: str, *, native_structured: bool = False) -> str:
    client = Anthropic(
        timeout=get_provider_timeout_seconds(),
        max_retries=0,
    )

    model = os.getenv("ANTHROPIC_MODEL", "claude-sonnet-5")

    request = {
        "model": model,
        "max_tokens": 1024,
        "messages": [
            {
                "role": "user",
                "content": prompt,
            }
        ],
    }

    if native_structured:
        request["output_config"] = _structured_output_config()

    message = _call_anthropic(lambda: client.messages.create(**request))

    input_tokens = message.usage.input_tokens or 0

    output_tokens = message.usage.output_tokens or 0

    log_usage(
        UsageRecord(
            provider="anthropic",
            model=model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_tokens=(input_tokens + output_tokens),
        )
    )

    if native_structured:
        _ensure_native_structured_message(message)

    return message.content[0].text


def ask_anthropic_document(
    document: DocumentContent,
    prompt: str,
    *,
    native_structured: bool = False,
) -> str:
    client = Anthropic(
        timeout=get_provider_timeout_seconds(),
        max_retries=0,
    )

    model = get_configured_document_model("anthropic")
    assert model is not None

    document_text = document.to_text()

    full_prompt = f"""
{prompt}

DOCUMENT CONTENT:

{document_text}
""".strip()

    content = []

    # Images first
    for image in document.images:
        image = normalize_image(image)

        if not image.media_type:
            continue

        encoded_image = base64.b64encode(image.data).decode("utf-8")

        content.append(
            {
                "type": "image",
                "source": {
                    "type": "base64",
                    "media_type": image.media_type,
                    "data": encoded_image,
                },
            }
        )

    # Text after images
    content.append(
        {
            "type": "text",
            "text": full_prompt,
        }
    )

    request = {
        "model": model,
        "max_tokens": 2048,
        "messages": [
            {
                "role": "user",
                "content": content,
            }
        ],
    }

    if native_structured:
        request["output_config"] = _structured_output_config()

    message = _call_anthropic(lambda: client.messages.create(**request))

    input_tokens = message.usage.input_tokens or 0

    output_tokens = message.usage.output_tokens or 0

    log_usage(
        UsageRecord(
            provider="anthropic",
            model=model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_tokens=(input_tokens + output_tokens),
        )
    )

    if native_structured:
        _ensure_native_structured_message(message)

    text_parts = []

    for block in message.content:
        if getattr(block, "type", None) == "text":
            text_parts.append(block.text)

    return "\n".join(text_parts)
