from .config import load_environment
from .providers.anthropic_provider import ask_anthropic
from .providers.gemini_provider import ask_gemini
from .providers.openai_provider import ask_openai

load_environment()


def ask_ai(provider: str, prompt: str) -> str:
    provider = provider.lower()

    if provider == "openai":
        return ask_openai(prompt)

    if provider in ("anthropic", "claude"):
        return ask_anthropic(prompt)

    if provider in ("gemini", "google"):
        return ask_gemini(prompt)

    raise ValueError(f"Unknown provider: {provider}. Use openai, anthropic, or gemini.")
