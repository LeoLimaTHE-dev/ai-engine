import base64
import os
from collections.abc import Callable
from typing import TypeVar

from openai import (
    APIConnectionError,
    APIStatusError,
    APITimeoutError,
    AuthenticationError,
    BadRequestError,
    NotFoundError,
    OpenAI,
    OpenAIError,
    PermissionDeniedError,
    RateLimitError,
)

from ai_engine.config import (
    get_provider_max_retries,
    get_provider_retry_base_delay_seconds,
    get_provider_retry_max_delay_seconds,
    get_provider_timeout_seconds,
)
from ai_engine.images import normalize_image
from ai_engine.models import DocumentContent
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


def _openai_error_metadata(exc: OpenAIError) -> dict[str, object]:
    response = getattr(exc, "response", None)
    headers = getattr(response, "headers", None)

    retry_after_seconds = None

    if headers is not None:
        retry_after_seconds = parse_retry_after_seconds(
            retry_after=headers.get("retry-after"),
            retry_after_ms=headers.get("retry-after-ms"),
        )

    error_code = getattr(exc, "code", None)

    if error_code is not None:
        error_code = str(error_code)

    return {
        "provider": "openai",
        "message": getattr(exc, "message", None) or str(exc) or "OpenAI request failed.",
        "status_code": getattr(exc, "status_code", None),
        "error_code": error_code,
        "retry_after_seconds": retry_after_seconds,
        "details": getattr(exc, "body", None),
    }


def _normalize_openai_error(exc: OpenAIError) -> ProviderError:
    metadata = _openai_error_metadata(exc)

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


def _call_openai(operation: Callable[[], ResultT]) -> ResultT:
    def call_once() -> ResultT:
        try:
            return operation()
        except OpenAIError as exc:
            raise _normalize_openai_error(exc) from exc

    return retry_provider_call(
        call_once,
        max_retries=get_provider_max_retries(),
        base_delay_seconds=get_provider_retry_base_delay_seconds(),
        max_delay_seconds=get_provider_retry_max_delay_seconds(),
    )


def ask_openai(prompt: str) -> str:
    client = OpenAI(
        timeout=get_provider_timeout_seconds(),
        max_retries=0,
    )

    model = os.getenv("OPENAI_MODEL", "gpt-5")

    response = _call_openai(
        lambda: client.responses.create(
            model=model,
            input=prompt,
        )
    )

    usage = response.usage

    if usage is not None:
        log_usage(
            UsageRecord(
                provider="openai",
                model=model,
                input_tokens=(usage.input_tokens or 0),
                output_tokens=(usage.output_tokens or 0),
                total_tokens=(usage.total_tokens or 0),
            )
        )

    return response.output_text


def ask_openai_document(
    document: DocumentContent,
    prompt: str,
) -> str:
    client = OpenAI(
        timeout=get_provider_timeout_seconds(),
        max_retries=0,
    )

    model = os.getenv(
        "OPENAI_MODEL",
        "gpt-5.6",
    )

    document_text = document.to_text()

    full_prompt = f"""
{prompt}

DOCUMENT CONTENT:

{document_text}
""".strip()

    content = [
        {
            "type": "input_text",
            "text": full_prompt,
        }
    ]

    for image in document.images:
        image = normalize_image(image)

        if not image.media_type:
            continue

        encoded_image = base64.b64encode(image.data).decode("utf-8")

        data_url = f"data:{image.media_type};base64,{encoded_image}"

        content.append(
            {
                "type": "input_image",
                "image_url": data_url,
            }
        )

    response = _call_openai(
        lambda: client.responses.create(
            model=model,
            input=[
                {
                    "role": "user",
                    "content": content,
                }
            ],
        )
    )
    usage = response.usage

    if usage is not None:
        log_usage(
            UsageRecord(
                provider="openai",
                model=model,
                input_tokens=(usage.input_tokens or 0),
                output_tokens=(usage.output_tokens or 0),
                total_tokens=(usage.total_tokens or 0),
            )
        )

    return response.output_text
