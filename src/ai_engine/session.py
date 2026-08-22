from dataclasses import dataclass, field

from ai_engine.models import DocumentContent


@dataclass
class ConversationMessage:
    role: str
    content: str


@dataclass
class ConversationSession:
    provider: str
    documents: list[DocumentContent]

    messages: list[ConversationMessage] = field(default_factory=list)

    summary: str = ""

    max_history_messages: int = 10
    summary_batch_size: int = 4
    # Messages removed from the recent history
    # are temporarily stored here until they
    # are summarized.
    pending_summary: list[ConversationMessage] = field(default_factory=list)

    def add_user_message(
        self,
        content: str,
    ) -> None:
        self.messages.append(
            ConversationMessage(
                role="user",
                content=content,
            )
        )

        self._trim_history()

    def add_assistant_message(
        self,
        content: str,
    ) -> None:
        self.messages.append(
            ConversationMessage(
                role="assistant",
                content=content,
            )
        )

        self._trim_history()

    def _trim_history(self) -> None:
        """
        Keeps recent messages in full.

        Older messages are moved to
        pending_summary instead of being lost.
        """

        while len(self.messages) > self.max_history_messages:
            message = self.messages.pop(0)

            self.pending_summary.append(message)

    @property
    def should_update_summary(self) -> bool:
        return len(self.pending_summary) >= self.summary_batch_size

    def get_pending_summary_text(
        self,
    ) -> str:
        parts: list[str] = []

        for message in self.pending_summary:
            if message.role == "user":
                label = "USER"
            else:
                label = "ASSISTANT"

            parts.append(f"{label}:\n{message.content}")

        return "\n\n".join(parts)

    def apply_summary(
        self,
        summary: str,
    ) -> None:
        self.summary = summary.strip()

        self.pending_summary.clear()

    def clear_history(self) -> None:
        self.messages.clear()
        self.pending_summary.clear()
        self.summary = ""

    def change_provider(
        self,
        provider: str,
        keep_history: bool = True,
    ) -> None:
        provider = provider.lower()

        allowed_providers = {
            "gemini",
            "google",
            "openai",
            "claude",
            "anthropic",
        }

        if provider not in allowed_providers:
            raise ValueError(f"Unsupported provider: {provider}")

        # Normalize aliases
        if provider == "google":
            provider = "gemini"

        if provider == "anthropic":
            provider = "claude"

        self.provider = provider

        if not keep_history:
            self.clear_history()

    @property
    def message_count(self) -> int:
        return len(self.messages)

    def build_conversation_prompt(
        self,
        current_user_message: str,
    ) -> str:
        parts: list[str] = []

        if self.summary:
            parts.append("SUMMARY OF EARLIER CONVERSATION:")

            parts.append(self.summary)

        if self.messages:
            parts.append("RECENT CONVERSATION:")

            for message in self.messages:
                if message.role == "user":
                    label = "USER"
                else:
                    label = "ASSISTANT"

                parts.append(f"{label}:\n{message.content}")

        parts.append("CURRENT USER REQUEST:")

        parts.append(current_user_message)

        return "\n\n".join(parts)
