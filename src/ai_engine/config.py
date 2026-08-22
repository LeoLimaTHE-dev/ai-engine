import math
import os
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[2]
ENV_FILE = PROJECT_ROOT / ".env"
DEFAULT_PROVIDER_TIMEOUT_SECONDS = 300.0
DEFAULT_PROVIDER_MAX_RETRIES = 2
DEFAULT_PROVIDER_RETRY_BASE_DELAY_SECONDS = 1.0
DEFAULT_PROVIDER_RETRY_MAX_DELAY_SECONDS = 10.0


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


def get_provider_max_retries() -> int:
    raw_value = os.getenv("AI_PROVIDER_MAX_RETRIES")

    if raw_value is None or not raw_value.strip():
        return DEFAULT_PROVIDER_MAX_RETRIES

    try:
        max_retries = int(raw_value)
    except ValueError as exc:
        raise ValueError(
            "AI_PROVIDER_MAX_RETRIES must be a non-negative integer"
        ) from exc

    if max_retries < 0:
        raise ValueError("AI_PROVIDER_MAX_RETRIES must be a non-negative integer")

    return max_retries


def _get_non_negative_float(name: str, default: float) -> float:
    raw_value = os.getenv(name)

    if raw_value is None or not raw_value.strip():
        return default

    try:
        value = float(raw_value)
    except ValueError as exc:
        raise ValueError(f"{name} must be a finite non-negative number") from exc

    if not math.isfinite(value) or value < 0:
        raise ValueError(f"{name} must be a finite non-negative number")

    return value


def get_provider_retry_base_delay_seconds() -> float:
    return _get_non_negative_float(
        "AI_PROVIDER_RETRY_BASE_DELAY_SECONDS",
        DEFAULT_PROVIDER_RETRY_BASE_DELAY_SECONDS,
    )


def get_provider_retry_max_delay_seconds() -> float:
    return _get_non_negative_float(
        "AI_PROVIDER_RETRY_MAX_DELAY_SECONDS",
        DEFAULT_PROVIDER_RETRY_MAX_DELAY_SECONDS,
    )
