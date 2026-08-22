from pathlib import Path

from ai_engine.models import DocumentContent

from .actions_prompt import (
    STRUCTURED_OUTPUT_INSTRUCTIONS,
)
from .batch import (
    process_batch_consolidated,
    process_batch_individual,
)
from .multimodal import ask_document
from .prompts import load_prompt
from .readers import read_documents
from .results import StructuredResult
from .structured import parse_structured_result

SUPPORTED_EXTENSIONS = {
    ".txt",
    ".md",
    ".markdown",
    ".csv",
    ".docx",
    ".pdf",
    ".xlsx",
    ".xlsm",
    ".png",
    ".jpg",
    ".jpeg",
    ".webp",
    ".bmp",
    ".gif",
    ".tiff",
    ".tif",
}


def collect_files(
    input_path: str | Path,
) -> list[Path]:
    """
    Receives either a single supported file
    or a directory containing supported files.
    """

    path = Path(input_path)

    if not path.exists():
        raise FileNotFoundError(f"Input not found: {path}")

    if path.is_file():
        if path.suffix.lower() not in SUPPORTED_EXTENSIONS:
            raise ValueError(f"Unsupported file type: {path.suffix}")

        return [path]

    files = [
        file
        for file in path.iterdir()
        if (file.is_file() and file.suffix.lower() in SUPPORTED_EXTENSIONS)
    ]

    files.sort()

    if not files:
        raise ValueError(f"No supported files found in: {path}")

    return files


def load_documents(
    input_path: str | Path,
) -> list[DocumentContent]:
    """
    Collects and reads all supported files.
    """

    files = collect_files(input_path)

    return read_documents(files)


def build_prompt(
    user_prompt: str,
    prompt_template: str | Path | None = None,
) -> str:
    """
    Builds the final user prompt.

    A saved prompt template is optional.
    """

    user_prompt = user_prompt.strip()

    if not user_prompt:
        raise ValueError("The user prompt cannot be empty.")

    if prompt_template is None:
        return user_prompt

    template = load_prompt(prompt_template)

    return f"""
{template}

---

INSTRUÇÃO ESPECÍFICA DO USUÁRIO:

{user_prompt}
""".strip()


def resolve_mode(
    mode: str,
    document_count: int,
) -> str:
    """
    Resolves auto mode.

    1 document:
        individual

    2+ documents:
        consolidated
    """

    mode = mode.lower()

    if mode == "auto":
        if document_count == 1:
            return "individual"

        return "consolidated"

    if mode not in (
        "individual",
        "consolidated",
    ):
        raise ValueError(
            f"Unknown mode: {mode}. Use auto, individual, or consolidated."
        )

    return mode


def run_workflow_documents(
    provider: str,
    documents: list[DocumentContent],
    user_prompt: str,
    mode: str = "auto",
    prompt_template: str | Path | None = None,
) -> str | dict[str, str]:
    """
    Runs a workflow using documents that have
    already been loaded.

    This prevents files from being read twice
    when preflight has already processed them.
    """

    if not documents:
        raise ValueError("No documents were provided.")

    final_prompt = build_prompt(
        user_prompt=user_prompt,
        prompt_template=prompt_template,
    )

    resolved_mode = resolve_mode(
        mode=mode,
        document_count=len(documents),
    )

    if resolved_mode == "individual":
        return process_batch_individual(
            provider=provider,
            documents=documents,
            prompt=final_prompt,
        )

    return process_batch_consolidated(
        provider=provider,
        documents=documents,
        prompt=final_prompt,
    )


def run_workflow(
    provider: str,
    input_path: str | Path,
    user_prompt: str,
    mode: str = "auto",
    prompt_template: str | Path | None = None,
) -> str | dict[str, str]:
    """
    Convenience workflow that reads the files
    automatically before processing them.
    """

    documents = load_documents(input_path)

    return run_workflow_documents(
        provider=provider,
        documents=documents,
        user_prompt=user_prompt,
        mode=mode,
        prompt_template=prompt_template,
    )


def run_structured_workflow_documents(
    provider: str,
    documents: list[DocumentContent],
    user_prompt: str,
    mode: str = "auto",
    prompt_template: str | Path | None = None,
) -> StructuredResult:
    """
    Structured workflow using documents that have
    already been loaded.

    Allows the AI to request supported output files.
    """

    if not documents:
        raise ValueError("No documents were provided.")

    user_prompt = user_prompt.strip()

    if not user_prompt:
        raise ValueError("The user prompt cannot be empty.")

    structured_prompt = f"""
{STRUCTURED_OUTPUT_INSTRUCTIONS}

USER REQUEST:

{user_prompt}
""".strip()

    final_prompt = build_prompt(
        user_prompt=structured_prompt,
        prompt_template=prompt_template,
    )

    resolved_mode = resolve_mode(
        mode=mode,
        document_count=len(documents),
    )

    # One document can be sent directly.
    # This avoids wrapping a JSON answer inside
    # the dictionary returned by batch individual.
    if resolved_mode == "individual" and len(documents) == 1:
        raw_response = ask_document(
            provider=provider,
            document=documents[0],
            prompt=final_prompt,
        )

        return parse_structured_result(raw_response)

    # Several documents + consolidated analysis.
    if resolved_mode == "consolidated":
        raw_response = process_batch_consolidated(
            provider=provider,
            documents=documents,
            prompt=final_prompt,
        )

        return parse_structured_result(raw_response)

    # Explicit individual mode with several files.
    # Each response is parsed independently and then
    # merged into one StructuredResult.
    raw_results = process_batch_individual(
        provider=provider,
        documents=documents,
        prompt=final_prompt,
    )

    messages: list[str] = []
    outputs = []

    for filename, raw_response in raw_results.items():
        parsed = parse_structured_result(raw_response)

        if parsed.message:
            messages.append(f"{filename}:\n{parsed.message}")

        outputs.extend(parsed.outputs)

    return StructuredResult(
        message="\n\n".join(messages),
        outputs=outputs,
    )


def run_structured_workflow(
    provider: str,
    input_path: str | Path,
    user_prompt: str,
    mode: str = "auto",
    prompt_template: str | Path | None = None,
) -> StructuredResult:
    """
    Convenience structured workflow that reads
    the input before processing.
    """

    documents = load_documents(input_path)

    return run_structured_workflow_documents(
        provider=provider,
        documents=documents,
        user_prompt=user_prompt,
        mode=mode,
        prompt_template=prompt_template,
    )
