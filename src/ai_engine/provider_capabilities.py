import os


_PROVIDER_ALIASES = {
    "openai": "openai",
    "anthropic": "anthropic",
    "claude": "anthropic",
    "gemini": "gemini",
    "google": "gemini",
}

_DOCUMENT_MODEL_CONFIGURATION = {
    "openai": ("OPENAI_MODEL", "gpt-5.6"),
    "anthropic": ("ANTHROPIC_MODEL", "claude-sonnet-5"),
    "gemini": ("GEMINI_MODEL", "gemini-3.7-flash"),
}

_NATIVE_STRUCTURED_MODELS = {
    "openai": frozenset({"gpt-5"}),
    "anthropic": frozenset({"claude-sonnet-5"}),
    "gemini": frozenset({"gemini-3.5-flash"}),
}


def normalize_provider(provider: str) -> str | None:
    return _PROVIDER_ALIASES.get(provider.lower())


def get_configured_document_model(provider: str) -> str | None:
    normalized_provider = normalize_provider(provider)

    if normalized_provider is None:
        return None

    environment_name, default_model = _DOCUMENT_MODEL_CONFIGURATION[
        normalized_provider
    ]
    return os.getenv(environment_name, default_model)


def supports_native_structured_output(provider: str, model: str | None) -> bool:
    normalized_provider = normalize_provider(provider)

    if normalized_provider is None or model is None:
        return False

    return model in _NATIVE_STRUCTURED_MODELS[normalized_provider]
