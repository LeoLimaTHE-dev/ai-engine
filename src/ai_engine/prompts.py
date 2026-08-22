from pathlib import Path

from .paths import get_paths

DEFAULT_PROMPTS_DIR = Path(r"C:\IA\4_Prompts")


SUPPORTED_PROMPT_EXTENSIONS = (
    ".md",
    ".txt",
)


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
        return prompt_path.read_text(encoding="utf-8").strip()

    # Search inside default prompts directory
    candidate = prompts_dir / prompt_path

    if candidate.exists():
        return candidate.read_text(encoding="utf-8").strip()

    # If no extension was provided,
    # try the supported extensions.
    if not prompt_path.suffix:
        for extension in SUPPORTED_PROMPT_EXTENSIONS:
            candidate = prompts_dir / f"{prompt_path.name}{extension}"

            if candidate.exists():
                return candidate.read_text(encoding="utf-8").strip()

    raise FileNotFoundError(f"Prompt not found: {prompt}")
