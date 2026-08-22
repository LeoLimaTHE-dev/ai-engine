import importlib.util
from pathlib import Path

import pytest

from ai_engine import (
    ProviderConnectionError,
    ProviderError,
    ProviderRateLimitError,
    ProviderRequestError,
    ProviderTimeoutError,
)

SCRIPT_PATH = Path(__file__).parents[1] / "application" / "ia_interativa.py"
SPEC = importlib.util.spec_from_file_location(
    "ia_interativa_provider_errors_test",
    SCRIPT_PATH,
)
assert SPEC is not None
assert SPEC.loader is not None
ia_interativa = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(ia_interativa)


def make_error(error_type, *, message="opaque", retryable=False, **metadata):
    return error_type(
        provider="gemini",
        message=message,
        retryable=retryable,
        **metadata,
    )


def test_rate_limit_with_retry_after_has_friendly_structured_message():
    error = make_error(
        ProviderRateLimitError,
        retryable=True,
        retry_after_seconds=34.58,
    )

    message = ia_interativa.format_error_for_user(error)

    assert "Provider: gemini" in message
    assert "limite de uso ou quota" in message
    assert "34.58 segundos" in message


def test_rate_limit_without_retry_after_does_not_invent_wait_time():
    error = make_error(ProviderRateLimitError)

    message = ia_interativa.format_error_for_user(error)

    assert "limite de uso ou quota" in message
    assert "aproximadamente" not in message


@pytest.mark.parametrize(
    "message",
    [
        "You exceeded your current quota with HTTP 429",
        "foo",
    ],
)
def test_gemini_rate_limit_category_depends_on_class_not_message(message):
    error = make_error(
        ProviderRateLimitError,
        message=message,
        status_code=429,
        error_code="RESOURCE_EXHAUSTED",
    )

    formatted = ia_interativa.format_error_for_user(error)

    assert "limite de uso ou quota" in formatted
    assert message not in formatted


def test_timeout_has_distinct_friendly_message():
    message = ia_interativa.format_error_for_user(
        make_error(ProviderTimeoutError, retryable=True)
    )

    assert "excedeu o tempo configurado" in message
    assert "quota" not in message


def test_connection_has_distinct_friendly_message():
    message = ia_interativa.format_error_for_user(
        make_error(ProviderConnectionError, retryable=True)
    )

    assert "Não foi possível comunicar" in message
    assert "quota" not in message


def test_request_error_exposes_status_and_code_but_not_details():
    error = make_error(
        ProviderRequestError,
        status_code=403,
        error_code="PERMISSION_DENIED",
        details={"secret-adjacent": "must not be printed"},
    )

    message = ia_interativa.format_error_for_user(error)

    assert "recusou a requisição" in message
    assert "Repetir sem alterar" in message
    assert "Status HTTP: 403" in message
    assert "Código do erro: PERMISSION_DENIED" in message
    assert "secret-adjacent" not in message


@pytest.mark.parametrize(
    ("retryable", "expected"),
    [
        (True, "A falha parece transitória."),
        (False, "A falha não foi classificada como transitória."),
    ],
)
def test_generic_provider_error_uses_retryable_metadata(retryable, expected):
    message = ia_interativa.format_error_for_user(
        make_error(ProviderError, retryable=retryable)
    )

    assert "A chamada ao provider falhou." in message
    assert expected in message
    assert "limite de uso ou quota" not in message


def test_provider_error_message_text_does_not_override_generic_category():
    error = make_error(
        ProviderError,
        message="429 quota rate limit",
        retryable=False,
    )

    message = ia_interativa.format_error_for_user(error)

    assert "A chamada ao provider falhou." in message
    assert "limite de uso ou quota" not in message


def test_non_provider_error_with_rate_limit_words_is_not_reclassified():
    error = RuntimeError("429 quota rate limit")

    assert ia_interativa.format_error_for_user(error) == "429 quota rate limit"


def test_application_source_has_no_provider_classification_by_error_text():
    source = SCRIPT_PATH.read_text(encoding="utf-8")

    assert '"429" in' not in source
    assert '"quota" in' not in source
    assert '"rate limit" in' not in source
    assert source.count("except ProviderError as exc:") == 2
