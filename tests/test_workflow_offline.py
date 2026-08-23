from pathlib import Path

import pytest

import ai_engine.workflow as workflow_module
from ai_engine.models import DocumentContent
from ai_engine.prompts import load_prompt


def make_documents(count):
    return [
        DocumentContent(
            source_path=Path(f"document-{index}.txt"),
            text=f"content-{index}",
        )
        for index in range(count)
    ]


def test_collect_files_sorts_supported_files_and_ignores_unsupported(tmp_path):
    expected = [
        tmp_path / "a.txt",
        tmp_path / "b.pdf",
        tmp_path / "c.md",
    ]
    for path in reversed(expected):
        path.write_text("content", encoding="utf-8")

    (tmp_path / "ignored.bin").write_bytes(b"ignored")
    nested = tmp_path / "nested"
    nested.mkdir()
    (nested / "nested.txt").write_text("nested", encoding="utf-8")

    assert workflow_module.collect_files(tmp_path) == expected


def test_collect_files_accepts_a_single_supported_file(tmp_path):
    path = tmp_path / "input.txt"
    path.write_text("content", encoding="utf-8")

    assert workflow_module.collect_files(path) == [path]


def test_collect_files_rejects_missing_input(tmp_path):
    with pytest.raises(FileNotFoundError, match="Input not found"):
        workflow_module.collect_files(tmp_path / "missing")


def test_collect_files_rejects_unsupported_single_file(tmp_path):
    path = tmp_path / "input.bin"
    path.write_bytes(b"content")

    with pytest.raises(ValueError, match="Unsupported file type: .bin"):
        workflow_module.collect_files(path)


def test_collect_files_rejects_directory_without_supported_files(tmp_path):
    (tmp_path / "ignored.bin").write_bytes(b"ignored")

    with pytest.raises(ValueError, match="No supported files found"):
        workflow_module.collect_files(tmp_path)


def test_load_documents_reads_the_collected_files_in_order(monkeypatch):
    input_path = Path("virtual-input")
    files = [Path("a.txt"), Path("b.md")]
    expected = make_documents(2)
    calls = []

    def fake_collect_files(received_path):
        calls.append(("collect", received_path))
        return files

    def fake_read_documents(received_files):
        calls.append(("read", received_files))
        return expected

    monkeypatch.setattr(workflow_module, "collect_files", fake_collect_files)
    monkeypatch.setattr(workflow_module, "read_documents", fake_read_documents)

    result = workflow_module.load_documents(input_path)

    assert result is expected
    assert calls == [
        ("collect", input_path),
        ("read", files),
    ]


def test_load_documents_allows_empty_or_unsupported_directory_only_when_opted_in(
    tmp_path,
):
    empty = tmp_path / "empty"
    empty.mkdir()
    unsupported = tmp_path / "unsupported"
    unsupported.mkdir()
    (unsupported / "notes.bin").write_bytes(b"not supported")

    assert workflow_module.load_documents(empty, allow_empty=True) == []
    assert workflow_module.load_documents(unsupported, allow_empty=True) == []

    with pytest.raises(ValueError, match="No supported files found"):
        workflow_module.load_documents(empty)


def test_load_documents_allow_empty_preserves_real_path_and_file_errors(tmp_path):
    missing = tmp_path / "missing"
    unsupported = tmp_path / "input.bin"
    unsupported.write_bytes(b"not supported")

    with pytest.raises(FileNotFoundError, match="Input not found"):
        workflow_module.load_documents(missing, allow_empty=True)

    with pytest.raises(ValueError, match="Unsupported file type: .bin"):
        workflow_module.load_documents(unsupported, allow_empty=True)


def test_load_documents_allow_empty_still_reads_supported_files(tmp_path):
    supported = tmp_path / "input.txt"
    supported.write_text("document content", encoding="utf-8")

    documents = workflow_module.load_documents(tmp_path, allow_empty=True)

    assert len(documents) == 1
    assert documents[0].source_path == supported
    assert documents[0].text == "document content"


def test_build_prompt_without_template_returns_trimmed_user_prompt():
    assert workflow_module.build_prompt("  Analyze this  ") == "Analyze this"


def test_build_prompt_combines_template_and_user_instruction(tmp_path):
    template = tmp_path / "analysis.md"
    template.write_text("  TEMPLATE INSTRUCTIONS  ", encoding="utf-8")

    result = workflow_module.build_prompt(
        user_prompt="  Compare the documents  ",
        prompt_template=template,
    )

    assert result == (
        "TEMPLATE INSTRUCTIONS\n\n"
        "---\n\n"
        "INSTRUÇÃO ESPECÍFICA DO USUÁRIO:\n\n"
        "Compare the documents"
    )


@pytest.mark.parametrize("user_prompt", ["", "   "])
def test_build_prompt_rejects_empty_user_prompt(user_prompt):
    with pytest.raises(ValueError, match="The user prompt cannot be empty"):
        workflow_module.build_prompt(user_prompt)


def test_load_prompt_accepts_an_existing_complete_path(tmp_path):
    path = tmp_path / "direct.md"
    path.write_text("  Direct template  ", encoding="utf-8")

    assert load_prompt(path) == "Direct template"


def test_load_prompt_resolves_name_with_supported_extension(tmp_path):
    path = tmp_path / "reusable.txt"
    path.write_text("  Reusable template  ", encoding="utf-8")

    assert load_prompt("reusable", prompts_dir=tmp_path) == "Reusable template"


def test_load_prompt_rejects_unknown_template(tmp_path):
    with pytest.raises(FileNotFoundError, match="Prompt not found: missing"):
        load_prompt("missing", prompts_dir=tmp_path)


@pytest.mark.parametrize(
    ("mode", "document_count", "expected"),
    [
        ("auto", 1, "individual"),
        ("auto", 2, "consolidated"),
        ("auto", 5, "consolidated"),
        ("individual", 2, "individual"),
        ("consolidated", 1, "consolidated"),
        ("AUTO", 1, "individual"),
    ],
)
def test_resolve_mode_returns_expected_mode(mode, document_count, expected):
    assert workflow_module.resolve_mode(mode, document_count) == expected


def test_resolve_mode_rejects_invalid_mode():
    with pytest.raises(ValueError, match="Unknown mode: invalid"):
        workflow_module.resolve_mode("invalid", 1)


@pytest.mark.parametrize(
    ("document_count", "expected_handler", "expected_result"),
    [
        (1, "individual", {"document-0.txt": "response"}),
        (2, "consolidated", "combined-response"),
    ],
)
def test_run_workflow_documents_auto_selects_handler(
    document_count,
    expected_handler,
    expected_result,
    monkeypatch,
):
    documents = make_documents(document_count)
    calls = []

    def fake_individual(provider, documents, prompt):
        calls.append(("individual", provider, documents, prompt))
        return {documents[0].filename: "response"}

    def fake_consolidated(provider, documents, prompt):
        calls.append(("consolidated", provider, documents, prompt))
        return "combined-response"

    monkeypatch.setattr(
        workflow_module,
        "process_batch_individual",
        fake_individual,
    )
    monkeypatch.setattr(
        workflow_module,
        "process_batch_consolidated",
        fake_consolidated,
    )

    result = workflow_module.run_workflow_documents(
        provider="openai",
        documents=documents,
        user_prompt="  Analyze  ",
        mode="auto",
    )

    assert result == expected_result
    assert calls == [
        (expected_handler, "openai", documents, "Analyze"),
    ]


def test_run_workflow_documents_passes_combined_template_prompt(
    monkeypatch,
    tmp_path,
):
    template = tmp_path / "template.md"
    template.write_text("Template", encoding="utf-8")
    documents = make_documents(1)
    calls = []

    def fake_individual(provider, documents, prompt):
        calls.append((provider, documents, prompt))
        return {documents[0].filename: "response"}

    monkeypatch.setattr(
        workflow_module,
        "process_batch_individual",
        fake_individual,
    )

    workflow_module.run_workflow_documents(
        provider="claude",
        documents=documents,
        user_prompt="Summarize",
        prompt_template=template,
    )

    assert calls == [
        (
            "claude",
            documents,
            "Template\n\n---\n\n"
            "INSTRUÇÃO ESPECÍFICA DO USUÁRIO:\n\nSummarize",
        )
    ]


def test_run_workflow_documents_rejects_empty_document_list():
    with pytest.raises(ValueError, match="No documents were provided"):
        workflow_module.run_workflow_documents(
            provider="openai",
            documents=[],
            user_prompt="Analyze",
        )


def test_run_workflow_documents_rejects_empty_prompt():
    with pytest.raises(ValueError, match="The user prompt cannot be empty"):
        workflow_module.run_workflow_documents(
            provider="openai",
            documents=make_documents(1),
            user_prompt="   ",
        )


def test_run_workflow_documents_rejects_invalid_mode():
    with pytest.raises(ValueError, match="Unknown mode: invalid"):
        workflow_module.run_workflow_documents(
            provider="openai",
            documents=make_documents(1),
            user_prompt="Analyze",
            mode="invalid",
        )


def test_run_workflow_delegates_loaded_documents_and_arguments(monkeypatch):
    input_path = Path("input-directory")
    documents = make_documents(2)
    calls = []
    expected = "workflow-response"

    def fake_load_documents(received_path):
        calls.append(("load", received_path))
        return documents

    def fake_run_workflow_documents(**kwargs):
        calls.append(("run", kwargs))
        return expected

    monkeypatch.setattr(workflow_module, "load_documents", fake_load_documents)
    monkeypatch.setattr(
        workflow_module,
        "run_workflow_documents",
        fake_run_workflow_documents,
    )

    result = workflow_module.run_workflow(
        provider="gemini",
        input_path=input_path,
        user_prompt="Compare",
        mode="individual",
        prompt_template="template-name",
    )

    assert result == expected
    assert calls == [
        ("load", input_path),
        (
            "run",
            {
                "provider": "gemini",
                "documents": documents,
                "user_prompt": "Compare",
                "mode": "individual",
                "prompt_template": "template-name",
            },
        ),
    ]
