import json
from pathlib import Path

from ai_engine.session import (
    ConversationMessage,
    ConversationSession,
)

from .paths import get_paths
from .prompts import validate_prompt_template_filename

DEFAULT_SESSIONS_DIR = Path(r"C:\IA\6_Dados\sessions")


def sanitize_session_name(
    name: str,
) -> str:
    name = name.strip()

    if not name:
        raise ValueError("Session name cannot be empty.")

    safe = "".join(
        char if (char.isalnum() or char in ("-", "_")) else "_" for char in name
    )

    return safe


def get_session_path(
    name: str,
    sessions_dir: str | Path | None = None,
) -> Path:
    if sessions_dir is None:
        sessions_dir = get_paths().sessions_dir

    sessions_dir = Path(sessions_dir)

    safe_name = sanitize_session_name(name)

    return sessions_dir / f"{safe_name}.json"


def save_session(
    name: str,
    session: ConversationSession,
    input_path: str | Path,
    sessions_dir: str | Path | None = None,
) -> Path:
    prompt_template = validate_prompt_template_filename(session.prompt_template)
    path = get_session_path(
        name=name,
        sessions_dir=sessions_dir,
    )

    path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    data = {
        "name": name,
        "provider": session.provider,
        "prompt_template": prompt_template,
        "input_path": str(Path(input_path)),
        "summary": session.summary,
        "max_history_messages": (session.max_history_messages),
        "summary_batch_size": (session.summary_batch_size),
        "messages": [
            {
                "role": message.role,
                "content": message.content,
            }
            for message in session.messages
        ],
        "pending_summary": [
            {
                "role": message.role,
                "content": message.content,
            }
            for message in session.pending_summary
        ],
    }

    path.write_text(
        json.dumps(
            data,
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    return path


def load_session_data(
    name: str,
    sessions_dir: str | Path | None = None,
) -> dict:
    path = get_session_path(
        name=name,
        sessions_dir=sessions_dir,
    )

    if not path.exists():
        raise FileNotFoundError(f"Session not found: {name}")

    return json.loads(path.read_text(encoding="utf-8"))


def list_sessions(
    sessions_dir: str | Path | None = None,
) -> list[str]:
    if sessions_dir is None:
        sessions_dir = get_paths().sessions_dir

    sessions_dir = Path(sessions_dir)

    if not sessions_dir.exists():
        return []

    names = [path.stem for path in sessions_dir.glob("*.json") if path.is_file()]

    names.sort()

    return names


def delete_session(
    name: str,
    sessions_dir: str | Path | None = None,
) -> bool:
    path = get_session_path(
        name=name,
        sessions_dir=sessions_dir,
    )

    if not path.exists():
        return False

    path.unlink()

    return True


def restore_conversation_session(
    data: dict,
    documents,
) -> ConversationSession:
    session = ConversationSession(
        provider=data["provider"],
        documents=documents,
        prompt_template=data.get("prompt_template"),
        max_history_messages=data.get(
            "max_history_messages",
            10,
        ),
        summary_batch_size=data.get(
            "summary_batch_size",
            4,
        ),
    )

    session.summary = data.get(
        "summary",
        "",
    )

    session.messages = [
        ConversationMessage(
            role=item["role"],
            content=item["content"],
        )
        for item in data.get("messages", [])
    ]

    session.pending_summary = [
        ConversationMessage(
            role=item["role"],
            content=item["content"],
        )
        for item in data.get("pending_summary", [])
    ]

    return session
