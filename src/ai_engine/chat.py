from ai_engine.results import StructuredResult
from ai_engine.router import ask_ai
from ai_engine.session import ConversationSession
from ai_engine.workflow import (
    run_structured_workflow_documents,
)

SUMMARY_INSTRUCTIONS = """
Create a compact memory of the conversation below.

Preserve information that may matter later, including:
- conclusions already reached;
- decisions made by the user;
- important facts from the documents;
- names, dates, values and identifiers when relevant;
- files or outputs already requested;
- unresolved questions;
- references that may be needed to understand
  later messages.

Do not reproduce the conversation verbatim.

Do not add new facts.

Return only the updated conversation summary.
""".strip()


def build_summary_prompt(
    session: ConversationSession,
) -> str:
    if not session.should_update_summary:
        return ""

    pending_text = session.get_pending_summary_text()

    parts = [
        SUMMARY_INSTRUCTIONS,
    ]

    if session.summary:
        parts.extend(
            [
                "",
                "EXISTING SUMMARY:",
                session.summary,
            ]
        )

    parts.extend(
        [
            "",
            "NEW OLDER MESSAGES:",
            pending_text,
        ]
    )

    return "\n".join(parts)


def summarize_session(
    session: ConversationSession,
) -> str | None:
    """
    Performs one text-only API request to compact
    older conversation messages.
    """

    if not session.should_update_summary:
        return None

    prompt = build_summary_prompt(session)

    response = ask_ai(
        provider=session.provider,
        prompt=prompt,
    )

    session.apply_summary(response)

    return response


def chat(
    session: ConversationSession,
    user_message: str,
    *,
    expect_outputs: bool = False,
) -> StructuredResult:
    """
    Executes one normal conversational API turn.

    expect_outputs explicitly controls whether the workflow requires the
    structured JSON contract; message text is never used to infer it.

    Memory compaction is intentionally NOT performed
    here because the interface must ask permission
    before every API request.
    """

    user_message = user_message.strip()

    if not user_message:
        raise ValueError("The message cannot be empty.")

    conversation_prompt = session.build_conversation_prompt(
        current_user_message=user_message,
    )

    result = run_structured_workflow_documents(
        provider=session.provider,
        documents=session.documents,
        user_prompt=conversation_prompt,
        mode="auto",
        prompt_template=session.prompt_template,
        expect_outputs=expect_outputs,
    )

    session.add_user_message(user_message)

    if result.message:
        session.add_assistant_message(result.message)

    return result
