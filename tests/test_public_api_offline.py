import subprocess
import sys
import textwrap

import ai_engine
from ai_engine import (
    OperationalPaths,
    PreflightReport,
    StructuredResult,
    analyze_documents,
    build_summary_prompt,
    execute_structured_result,
    format_preflight,
    format_usage_summary,
    get_paths,
    get_usage_totals,
    load_documents,
    summarize_session,
    usage_difference,
)
from ai_engine.actions import execute_structured_result as actions_execute
from ai_engine.chat import (
    build_summary_prompt as chat_build_summary_prompt,
    summarize_session as chat_summarize_session,
)
from ai_engine.limits import (
    PreflightReport as limits_preflight_report,
    analyze_documents as limits_analyze_documents,
    format_preflight as limits_format_preflight,
)
from ai_engine.paths import OperationalPaths as paths_operational_paths
from ai_engine.paths import get_paths as paths_get_paths
from ai_engine.results import StructuredResult as results_structured_result
from ai_engine.usage import (
    format_usage_summary as usage_format_summary,
    get_usage_totals as usage_get_totals,
    usage_difference as usage_get_difference,
)
from ai_engine.workflow import load_documents as workflow_load_documents


PREVIOUS_PUBLIC_NAMES = {
    "ask_ai",
    "ask_document",
    "combine_documents",
    "load_prompt",
    "process_batch_consolidated",
    "process_batch_individual",
    "run_structured_workflow",
    "run_structured_workflow_documents",
    "run_workflow",
    "run_workflow_documents",
    "chat",
    "ConversationMessage",
    "ConversationSession",
    "delete_session",
    "list_sessions",
    "load_session_data",
    "restore_conversation_session",
    "save_session",
}

NEW_PUBLIC_NAMES = {
    "OperationalPaths",
    "PreflightReport",
    "StructuredResult",
    "get_paths",
    "load_documents",
    "analyze_documents",
    "format_preflight",
    "build_summary_prompt",
    "summarize_session",
    "execute_structured_result",
    "get_usage_totals",
    "usage_difference",
    "format_usage_summary",
}


def test_public_api_preserves_previous_names_and_exposes_new_names():
    public_names = set(ai_engine.__all__)

    assert PREVIOUS_PUBLIC_NAMES <= public_names
    assert NEW_PUBLIC_NAMES <= public_names

    for name in NEW_PUBLIC_NAMES:
        assert getattr(ai_engine, name) is not None


def test_new_reexports_are_the_objects_from_their_origin_modules():
    expected_identities = {
        OperationalPaths: paths_operational_paths,
        PreflightReport: limits_preflight_report,
        StructuredResult: results_structured_result,
        get_paths: paths_get_paths,
        load_documents: workflow_load_documents,
        analyze_documents: limits_analyze_documents,
        format_preflight: limits_format_preflight,
        build_summary_prompt: chat_build_summary_prompt,
        summarize_session: chat_summarize_session,
        execute_structured_result: actions_execute,
        get_usage_totals: usage_get_totals,
        usage_difference: usage_get_difference,
        format_usage_summary: usage_format_summary,
    }

    for public_object, origin_object in expected_identities.items():
        assert public_object is origin_object


def test_interactive_preflight_confirmation_is_not_in_public_all():
    assert "confirm_preflight" not in ai_engine.__all__


def test_clean_process_import_has_no_cycle_application_or_external_call():
    source = textwrap.dedent(
        """
        import socket
        import sys

        import anthropic
        import openai
        from google import genai

        class ForbiddenClient:
            def __init__(self, *args, **kwargs):
                raise AssertionError("provider client instantiated during import")

        def forbidden_network(*args, **kwargs):
            raise AssertionError("network attempted during import")

        anthropic.Anthropic = ForbiddenClient
        openai.OpenAI = ForbiddenClient
        genai.Client = ForbiddenClient
        socket.create_connection = forbidden_network
        socket.socket.connect = forbidden_network

        import ai_engine

        assert "application.ia_interativa" not in sys.modules
        assert all(getattr(ai_engine, name) is not None for name in ai_engine.__all__)
        """
    )

    completed = subprocess.run(
        [sys.executable, "-c", source],
        capture_output=True,
        text=True,
        check=False,
    )

    assert completed.returncode == 0, completed.stderr
