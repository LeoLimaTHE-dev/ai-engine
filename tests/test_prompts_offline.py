from pathlib import Path

from ai_engine.prompts import (
    PromptTemplate,
    discover_prompt_templates,
    load_prompt,
)


OFFICIAL_TEMPLATES = {
    "resumir.md": (
        "Resumir",
        "Produz uma síntese objetiva do material, preservando os fatos relevantes.",
    ),
    "analisar_documentos.md": (
        "Analisar documentos",
        "Correlaciona os arquivos e identifica fatos, divergências, lacunas e pontos relevantes.",
    ),
    "comparar_arquivos.md": (
        "Comparar arquivos",
        "Compara informações equivalentes e destaca convergências, divergências e ausências.",
    ),
    "relatorio_multimodal_com_imagens.md": (
        "Relatório multimodal com imagens",
        "Produz relatório e referencia imagens relevantes para inserção manual.",
    ),
}


def _write_template(
    directory: Path,
    filename: str,
    name: str,
    description: str,
    body: str = "Instruções efetivas.",
) -> None:
    (directory / filename).write_text(
        f"# {name}\n> Descrição: {description}\n\n{body}\n",
        encoding="utf-8",
    )


def test_discovery_returns_the_four_official_templates_in_name_order(tmp_path):
    for filename, (name, description) in reversed(OFFICIAL_TEMPLATES.items()):
        _write_template(tmp_path, filename, name, description)

    templates = discover_prompt_templates(tmp_path)

    assert templates == [
        PromptTemplate(filename=filename, name=name, description=description)
        for filename, (name, description) in sorted(
            OFFICIAL_TEMPLATES.items(),
            key=lambda item: item[1][0].casefold(),
        )
    ]


def test_discovery_supports_markdown_and_text_templates(tmp_path):
    _write_template(tmp_path, "markdown.md", "Markdown", "Template Markdown.")
    _write_template(tmp_path, "text.txt", "Texto", "Template de texto.")

    assert [item.filename for item in discover_prompt_templates(tmp_path)] == [
        "markdown.md",
        "text.txt",
    ]


def test_discovery_ignores_files_without_valid_metadata(tmp_path):
    (tmp_path / "experimental.md").write_text(
        "Instrução experimental sem metadata.",
        encoding="utf-8",
    )
    (tmp_path / "missing-description.md").write_text(
        "# Sem descrição\n\nCorpo.",
        encoding="utf-8",
    )
    (tmp_path / "empty-name.txt").write_text(
        "# \n> Descrição: Inválido.\n\nCorpo.",
        encoding="utf-8",
    )
    (tmp_path / "ignored.json").write_text(
        '{"name": "Ignored"}',
        encoding="utf-8",
    )

    assert discover_prompt_templates(tmp_path) == []


def test_invalid_file_does_not_break_discovery(monkeypatch, tmp_path):
    _write_template(tmp_path, "valid.md", "Válido", "Descrição válida.")
    unreadable = tmp_path / "unreadable.md"
    unreadable.write_text("# Inválido\n> Descrição: Não será lido.", encoding="utf-8")
    original_read_text = Path.read_text

    def fake_read_text(path, *args, **kwargs):
        if path == unreadable:
            raise OSError("cannot read")
        return original_read_text(path, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", fake_read_text)

    assert [item.filename for item in discover_prompt_templates(tmp_path)] == [
        "valid.md"
    ]


def test_discovery_uses_the_dynamic_operational_prompts_directory(
    monkeypatch,
    tmp_path,
):
    prompts_dir = tmp_path / "4_Prompts"
    prompts_dir.mkdir()
    _write_template(prompts_dir, "dynamic.md", "Dinâmico", "Descrição dinâmica.")
    monkeypatch.setenv("IA_ROOT", str(tmp_path))

    assert discover_prompt_templates() == [
        PromptTemplate(
            filename="dynamic.md",
            name="Dinâmico",
            description="Descrição dinâmica.",
        )
    ]


def test_load_prompt_preserves_legacy_content_without_metadata(tmp_path):
    path = tmp_path / "legacy.md"
    path.write_text("  Legacy prompt instructions.  ", encoding="utf-8")

    assert load_prompt(path) == "Legacy prompt instructions."


def test_load_prompt_removes_valid_presentation_metadata(tmp_path):
    _write_template(
        tmp_path,
        "official.md",
        "Nome humano",
        "Descrição apenas para o menu.",
        body="Primeira instrução.\n\nSegunda instrução.",
    )

    instructions = load_prompt("official", prompts_dir=tmp_path)

    assert instructions == "Primeira instrução.\n\nSegunda instrução."
    assert "Nome humano" not in instructions
    assert "Descrição apenas para o menu" not in instructions


def test_missing_prompts_directory_has_no_discoverable_templates(tmp_path):
    assert discover_prompt_templates(tmp_path / "missing") == []
