from pathlib import Path

import pytest

from ai_engine.limits import (
    PreflightReport,
    analyze_documents,
    confirm_preflight,
    format_preflight,
)
from ai_engine.models import DocumentContent, DocumentImage


LIMIT_ENV = {
    "AI_WARN_ESTIMATED_TEXT_TOKENS": "1000",
    "AI_MAX_ESTIMATED_TEXT_TOKENS": "2000",
    "AI_WARN_IMAGES": "1000",
    "AI_MAX_IMAGES": "2000",
    "AI_MAX_BATCH_FILES": "2000",
    "AI_WARN_IMAGE_MB": "1000",
    "AI_MAX_IMAGE_MB": "2000",
}


def set_limits(monkeypatch, **overrides):
    values = {**LIMIT_ENV, **{key: str(value) for key, value in overrides.items()}}
    for name, value in values.items():
        monkeypatch.setenv(name, value)


@pytest.mark.parametrize(
    ("errors", "expected_allowed"),
    [
        ([], True),
        (["blocked"], False),
    ],
)
def test_preflight_report_allowed_reflects_errors(errors, expected_allowed):
    report = PreflightReport(
        file_count=1,
        text_characters=4,
        estimated_text_tokens=1,
        image_count=0,
        image_bytes=0,
        errors=errors,
    )

    assert report.allowed is expected_allowed


def test_analyze_documents_counts_text_and_extra_text(monkeypatch):
    set_limits(monkeypatch)
    documents = [
        DocumentContent(source_path=Path("first.txt"), text="12345678"),
        DocumentContent(source_path=Path("second.txt"), text="abcd"),
    ]

    without_extra = analyze_documents(documents)
    with_extra = analyze_documents(documents, extra_text="12345")

    assert without_extra.file_count == 2
    assert without_extra.text_characters == 12
    assert without_extra.estimated_text_tokens == 3
    assert with_extra.text_characters == 17
    assert with_extra.estimated_text_tokens == 5


def test_analyze_documents_counts_image_bytes_and_megabytes(monkeypatch):
    set_limits(monkeypatch)
    document = DocumentContent(
        source_path=Path("images.docx"),
        images=[
            DocumentImage(name="first.png", data=b"a" * 1024),
            DocumentImage(name="second.png", data=b"b" * 2048),
        ],
    )

    report = analyze_documents([document])

    assert report.image_count == 2
    assert report.image_bytes == 3072
    assert report.image_megabytes == pytest.approx(3072 / 1024 / 1024)


def test_analyze_documents_uses_environment_thresholds_for_warnings(monkeypatch):
    set_limits(
        monkeypatch,
        AI_WARN_ESTIMATED_TEXT_TOKENS=2,
        AI_WARN_IMAGES=1,
        AI_WARN_IMAGE_MB=1,
    )
    document = DocumentContent(
        source_path=Path("warning.txt"),
        text="12345678",
        images=[DocumentImage(name="large.png", data=b"x" * 1024 * 1024)],
    )

    report = analyze_documents([document])

    assert report.warnings == [
        "Estimated text-token count is high.",
        "Large number of images.",
        "Large image payload.",
    ]
    assert report.errors == []
    assert report.allowed is True


def test_analyze_documents_reports_each_exceeded_maximum(monkeypatch):
    set_limits(
        monkeypatch,
        AI_WARN_ESTIMATED_TEXT_TOKENS=1000,
        AI_MAX_ESTIMATED_TEXT_TOKENS=1,
        AI_WARN_IMAGES=1000,
        AI_MAX_IMAGES=0,
        AI_MAX_BATCH_FILES=0,
        AI_WARN_IMAGE_MB=1000,
        AI_MAX_IMAGE_MB=0,
    )
    document = DocumentContent(
        source_path=Path("blocked.txt"),
        text="12345678",
        images=[DocumentImage(name="image.png", data=b"x")],
    )

    report = analyze_documents([document])

    assert report.errors == [
        "Estimated text-token limit exceeded.",
        "Maximum image count exceeded.",
        "Maximum image payload exceeded.",
        "Maximum batch file count exceeded.",
    ]
    assert report.allowed is False


def test_format_preflight_includes_metrics_warnings_and_errors():
    report = PreflightReport(
        file_count=2,
        text_characters=1234,
        estimated_text_tokens=309,
        image_count=3,
        image_bytes=1024 * 1024,
        warnings=["Warning message"],
        errors=["Error message"],
    )

    formatted = format_preflight(report)

    assert "Arquivos: 2" in formatted
    assert "Caracteres de texto: 1,234" in formatted
    assert "Tokens de texto estimados: 309" in formatted
    assert "Imagens: 3" in formatted
    assert "Imagens (MB): 1.00" in formatted
    assert "AVISOS:\n- Warning message" in formatted
    assert "BLOQUEIOS:\n- Error message" in formatted


def make_confirmation_report(errors=None):
    return PreflightReport(
        file_count=1,
        text_characters=4,
        estimated_text_tokens=1,
        image_count=0,
        image_bytes=0,
        errors=errors or [],
    )


def test_confirm_preflight_accepts_normal_confirmation(monkeypatch):
    monkeypatch.setattr("builtins.input", lambda prompt: "s")

    assert confirm_preflight(make_confirmation_report()) is True


@pytest.mark.parametrize("choice", ["", "n"])
def test_confirm_preflight_rejects_normal_cancellation(choice, monkeypatch):
    monkeypatch.setattr("builtins.input", lambda prompt: choice)

    assert confirm_preflight(make_confirmation_report()) is False


@pytest.mark.parametrize(
    ("choice", "expected"),
    [
        ("CONFIRMAR", True),
        ("confirmar", False),
    ],
)
def test_confirm_preflight_above_limit_requires_exact_confirmation(
    choice,
    expected,
    monkeypatch,
):
    monkeypatch.setattr("builtins.input", lambda prompt: choice)
    report = make_confirmation_report(errors=["Maximum exceeded"])

    assert confirm_preflight(report) is expected

