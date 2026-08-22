import base64
import os

from openai import OpenAI

from ai_engine.images import normalize_image
from ai_engine.models import DocumentContent
from ai_engine.usage import (
    UsageRecord,
    log_usage,
)


def ask_openai(prompt: str) -> str:
    client = OpenAI()

    model = os.getenv("OPENAI_MODEL", "gpt-5")

    response = client.responses.create(
        model=model,
        input=prompt,
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
    client = OpenAI()

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

    response = client.responses.create(
        model=model,
        input=[
            {
                "role": "user",
                "content": content,
            }
        ],
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
