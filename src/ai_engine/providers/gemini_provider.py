import base64
import os

from google import genai

from ai_engine.images import normalize_image
from ai_engine.models import DocumentContent
from ai_engine.usage import (
    UsageRecord,
    log_usage,
)


def ask_gemini(prompt: str) -> str:
    client = genai.Client()

    model = os.getenv("GEMINI_MODEL", "gemini-3.6-flash")

    interaction = client.interactions.create(
        model=model,
        input=prompt,
    )

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

    return interaction.output_text


def ask_gemini_document(
    document: DocumentContent,
    prompt: str,
) -> str:
    client = genai.Client()

    model = os.getenv(
        "GEMINI_MODEL",
        "gemini-3.7-flash",
    )

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

    interaction = client.interactions.create(
        model=model,
        input=inputs,
    )

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

    return interaction.output_text
