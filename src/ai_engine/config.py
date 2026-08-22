import math
import os
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[2]
ENV_FILE = PROJECT_ROOT / ".env"
DEFAULT_PROVIDER_TIMEOUT_SECONDS = 300.0


def load_environment() -> None:
    load_dotenv(ENV_FILE)


def get_provider_timeout_seconds() -> float:
    raw_value = os.getenv("AI_PROVIDER_TIMEOUT_SECONDS")

    if raw_value is None or not raw_value.strip():
        return DEFAULT_PROVIDER_TIMEOUT_SECONDS

    try:
        timeout = float(raw_value)
    except ValueError as exc:
        raise ValueError(
            "AI_PROVIDER_TIMEOUT_SECONDS must be a positive finite number"
        ) from exc

    if not math.isfinite(timeout) or timeout <= 0:
        raise ValueError(
            "AI_PROVIDER_TIMEOUT_SECONDS must be a positive finite number"
        )

    return timeout
