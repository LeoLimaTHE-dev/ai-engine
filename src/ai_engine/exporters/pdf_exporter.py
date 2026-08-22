from pathlib import Path

from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import (
    Paragraph,
    SimpleDocTemplate,
    Spacer,
)


def save_pdf(
    content: str,
    output_path: str | Path,
    title: str | None = None,
) -> Path:
    path = Path(output_path)

    path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    document = SimpleDocTemplate(
        str(path),
        pagesize=A4,
    )

    styles = getSampleStyleSheet()

    elements = []

    if title:
        elements.append(
            Paragraph(
                title,
                styles["Title"],
            )
        )

        elements.append(Spacer(1, 12))

    paragraphs = content.splitlines()

    for paragraph in paragraphs:
        paragraph = paragraph.strip()

        if not paragraph:
            elements.append(Spacer(1, 8))
            continue

        # Avoid interpreting user/model text as ReportLab markup
        safe_text = (
            paragraph.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        )

        elements.append(
            Paragraph(
                safe_text,
                styles["BodyText"],
            )
        )

        elements.append(Spacer(1, 6))

    document.build(elements)

    return path
