from dataclasses import dataclass
from pathlib import Path

from .paths import get_paths

DEFAULT_PROMPTS_DIR = Path(r"C:\IA\4_Prompts")


SUPPORTED_PROMPT_EXTENSIONS = (
    ".md",
    ".txt",
)

DESCRIPTION_PREFIX = "> Descrição: "


@dataclass(frozen=True, slots=True)
class PromptTemplate:
    filename: str
    name: str
    description: str


def validate_prompt_template_filename(filename: str | None) -> str | None:
    """Validate the filename-only reference persisted by a session."""

    if filename is None:
        return None

    if not isinstance(filename, str):
        raise TypeError("prompt_template must be a filename string or None")

    if (
        not filename
        or filename != filename.strip()
        or Path(filename).name != filename
        or Path(filename).suffix.lower() not in SUPPORTED_PROMPT_EXTENSIONS
    ):
        raise ValueError("prompt_template must be a .md or .txt filename")

    return filename


def _split_prompt_metadata(
    content: str,
) -> tuple[tuple[str, str] | None, str]:
    lines = content.splitlines()

    if len(lines) < 2:
        return None, content.strip()

    heading = lines[0].strip()
    description_line = lines[1].strip()

    if not heading.startswith("# ") or not description_line.startswith(
        DESCRIPTION_PREFIX
    ):
        return None, content.strip()

    name = heading[2:].strip()
    description = description_line[len(DESCRIPTION_PREFIX) :].strip()

    if not name or not description:
        return None, content.strip()

    return (name, description), "\n".join(lines[2:]).strip()


def discover_prompt_templates(
    prompts_dir: str | Path | None = None,
) -> list[PromptTemplate]:
    """Return valid menu templates from the configured prompts directory."""

    if prompts_dir is None:
        prompts_dir = get_paths().prompts_dir

    directory = Path(prompts_dir)

    if not directory.exists():
        return []

    templates: list[PromptTemplate] = []

    for path in directory.iterdir():
        if (
            not path.is_file()
            or path.suffix.lower() not in SUPPORTED_PROMPT_EXTENSIONS
        ):
            continue

        try:
            content = path.read_text(encoding="utf-8")
        except (OSError, UnicodeError):
            continue

        metadata, _ = _split_prompt_metadata(content)

        if metadata is None:
            continue

        name, description = metadata

        templates.append(
            PromptTemplate(
                filename=path.name,
                name=name,
                description=description,
            )
        )

    templates.sort(
        key=lambda item: (item.name.casefold(), item.filename.casefold())
    )
    return templates


def load_prompt(
    prompt: str | Path,
    prompts_dir: str | Path | None = None,
) -> str:
    """
    Loads a reusable prompt.

    Accepts:
    - a prompt name, e.g. "analisar_documentos"
    - a file name, e.g. "analisar_documentos.md"
    - a complete file path
    """

    if prompts_dir is None:
        prompts_dir = get_paths().prompts_dir

    prompts_dir = Path(prompts_dir)
    prompt_path = Path(prompt)

    # Complete/existing path
    if prompt_path.exists():
        return _load_prompt_content(prompt_path)

    # Search inside default prompts directory
    candidate = prompts_dir / prompt_path

    if candidate.exists():
        return _load_prompt_content(candidate)

    # If no extension was provided,
    # try the supported extensions.
    if not prompt_path.suffix:
        for extension in SUPPORTED_PROMPT_EXTENSIONS:
            candidate = prompts_dir / f"{prompt_path.name}{extension}"

            if candidate.exists():
                return _load_prompt_content(candidate)

    raise FileNotFoundError(f"Prompt not found: {prompt}")


def _load_prompt_content(path: Path) -> str:
    content = path.read_text(encoding="utf-8")
    _, instructions = _split_prompt_metadata(content)
    return instructions
