import math
import os
from dataclasses import dataclass, field

from ai_engine.models import DocumentContent


@dataclass
class PreflightReport:
    file_count: int

    text_characters: int

    estimated_text_tokens: int

    image_count: int

    image_bytes: int

    warnings: list[str] = field(default_factory=list)

    errors: list[str] = field(default_factory=list)

    @property
    def image_megabytes(self) -> float:
        return self.image_bytes / 1024 / 1024

    @property
    def allowed(self) -> bool:
        return not self.errors


def env_int(
    name: str,
    default: int,
) -> int:
    value = os.getenv(name)

    if value is None:
        return default

    return int(value)


def analyze_documents(
    documents: list[DocumentContent],
    extra_text: str = "",
) -> PreflightReport:
    text_characters = sum(len(document.to_text()) for document in documents) + len(
        extra_text
    )

    # Estimativa local aproximada.
    # O consumo real será registrado depois pela API.
    estimated_text_tokens = math.ceil(text_characters / 4)

    images = [image for document in documents for image in document.images]

    image_count = len(images)

    image_bytes = sum(len(image.data) for image in images)

    report = PreflightReport(
        file_count=len(documents),
        text_characters=text_characters,
        estimated_text_tokens=estimated_text_tokens,
        image_count=image_count,
        image_bytes=image_bytes,
    )

    warn_tokens = env_int(
        "AI_WARN_ESTIMATED_TEXT_TOKENS",
        40_000,
    )

    max_tokens = env_int(
        "AI_MAX_ESTIMATED_TEXT_TOKENS",
        120_000,
    )

    warn_images = env_int(
        "AI_WARN_IMAGES",
        10,
    )

    max_images = env_int(
        "AI_MAX_IMAGES",
        30,
    )

    max_files = env_int(
        "AI_MAX_BATCH_FILES",
        30,
    )

    warn_image_mb = env_int(
        "AI_WARN_IMAGE_MB",
        20,
    )

    max_image_mb = env_int(
        "AI_MAX_IMAGE_MB",
        60,
    )

    if estimated_text_tokens >= warn_tokens:
        report.warnings.append("Estimated text-token count is high.")

    if estimated_text_tokens > max_tokens:
        report.errors.append("Estimated text-token limit exceeded.")

    if image_count >= warn_images:
        report.warnings.append("Large number of images.")

    if image_count > max_images:
        report.errors.append("Maximum image count exceeded.")

    if report.image_megabytes >= warn_image_mb:
        report.warnings.append("Large image payload.")

    if report.image_megabytes > max_image_mb:
        report.errors.append("Maximum image payload exceeded.")

    if report.file_count > max_files:
        report.errors.append("Maximum batch file count exceeded.")

    return report


def format_preflight(
    report: PreflightReport,
) -> str:
    lines = [
        "===== PREFLIGHT =====",
        (f"Arquivos: {report.file_count}"),
        (f"Caracteres de texto: {report.text_characters:,}"),
        (f"Tokens de texto estimados: {report.estimated_text_tokens:,}"),
        (f"Imagens: {report.image_count}"),
        (f"Imagens (MB): {report.image_megabytes:.2f}"),
    ]

    if report.warnings:
        lines.append("")
        lines.append("AVISOS:")

        for warning in report.warnings:
            lines.append(f"- {warning}")

    if report.errors:
        lines.append("")
        lines.append("BLOQUEIOS:")

        for error in report.errors:
            lines.append(f"- {error}")

    return "\n".join(lines)


def confirm_preflight(
    report: PreflightReport,
) -> bool:
    """
    Always asks the user for confirmation before
    an API request.

    Normal or warning-level requests:
        requires s/sim/y/yes.

    Requests above configured maximum limits:
        requires the explicit word CONFIRMAR.
    """

    print()
    print(format_preflight(report))

    print()

    # --------------------------------
    # Above maximum configured limits
    # --------------------------------

    if report.errors:
        print("=" * 60)
        print("ATENÇÃO: A REQUISIÇÃO ULTRAPASSA OS LIMITES CONFIGURADOS.")
        print("=" * 60)

        print()
        print(
            "Ela ainda pode ser executada, "
            "mas poderá consumir uma quantidade "
            "elevada de tokens ou recursos."
        )

        print()

        choice = input('Digite "CONFIRMAR" para continuar: ').strip()

        return choice == "CONFIRMAR"

    # --------------------------------
    # Normal / warning-level request
    # --------------------------------

    choice = input("Continuar com a chamada da API? [s/N]: ").strip().lower()

    return choice in (
        "s",
        "sim",
        "y",
        "yes",
    )
