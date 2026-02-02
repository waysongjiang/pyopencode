from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class CompactionPolicy:
    """Policy knobs for keeping the prompt within a reasonable size.

    This is intentionally simple and dependency-free.
    """

    # Maximum number of messages to send to the model (after compaction).
    max_messages: int = 45

    # If we exceed max_messages, summarize earlier content into a system summary.
    summarize_when_over: int = 60

    # Max characters for a single tool result kept in the session/prompt.
    max_tool_result_chars: int = 12000

    # Max characters for assistant/user messages (safety against huge pastes).
    max_message_chars: int = 20000
