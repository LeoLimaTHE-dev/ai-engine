import base64
import os

from anthropic import Anthropic

from ai_engine.images import normalize_image
from ai_engine.models import DocumentContent
from ai_engine.usage import (
    UsageRecord,
    log_usage,
)


def ask_anthropic(prompt: str) -> str:
    client = Anthropic()

    model = os.getenv("ANTHROPIC_MODEL", "claude-sonnet-5")

    message = client.messages.create(
        model=model,
        max_tokens=1024,
        messages=[
            {
                "role": "user",
                "content": prompt,
            }
        ],
    )

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

    return message.content[0].text


def ask_anthropic_document(
    document: DocumentContent,
    prompt: str,
) -> str:
    client = Anthropic()

    model = os.getenv(
        "ANTHROPIC_MODEL",
        "claude-sonnet-5",
    )

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

    message = client.messages.create(
        model=model,
        max_tokens=2048,
        messages=[
            {
                "role": "user",
                "content": content,
            }
        ],
    )

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

    text_parts = []

    for block in message.content:
        if getattr(block, "type", None) == "text":
            text_parts.append(block.text)

    return "\n".join(text_parts)
