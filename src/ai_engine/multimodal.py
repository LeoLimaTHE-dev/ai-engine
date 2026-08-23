from ai_engine.models import DocumentContent

from .providers.anthropic_provider import ask_anthropic_document
from .providers.gemini_provider import ask_gemini_document
from .providers.openai_provider import ask_openai_document


def ask_document(
    provider: str,
    document: DocumentContent,
    prompt: str,
    *,
    native_structured: bool = False,
) -> str:
    provider = provider.lower()

    if provider in ("gemini", "google"):
        return ask_gemini_document(
            document=document,
            prompt=prompt,
        )

    if provider == "openai":
        if native_structured:
            return ask_openai_document(
                document=document,
                prompt=prompt,
                native_structured=True,
            )

        return ask_openai_document(
            document=document,
            prompt=prompt,
        )

    if provider in ("anthropic", "claude"):
        return ask_anthropic_document(
            document=document,
            prompt=prompt,
        )

    raise ValueError(
        f"Unknown multimodal provider: {provider}. Use gemini, openai, or anthropic."
    )
