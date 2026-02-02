from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol

from ..session.models import Message


class ChatProvider(Protocol):
    def chat(self, messages: list[dict[str, Any]], tools: list[dict] | None = None): ...


@dataclass
class SummaryResult:
    text: str
    is_error: bool = False


SUMMARY_PROMPT = (
    "You are summarizing a coding agent conversation for future continuation.\n"
    "Write a concise but information-dense summary with these sections:\n"
    "- Goal\n- Key decisions\n- Current state (files touched, commands run, errors)\n- TODO next\n"
    "Keep it under 2500 characters."
)


def summarize(
    provider: ChatProvider,
    messages: list[Message],
    include_reasoning_content: bool,
    *,
    force_reasoning_content: bool = False,
) -> SummaryResult:
    """Ask the current provider to summarize previous messages.

    We intentionally do NOT pass tools to avoid tool calls.
    """
    try:
        oai_msgs = [{"role": "system", "content": SUMMARY_PROMPT}]
        oai_msgs.extend(
            [
                m.to_openai(
                    include_reasoning_content=include_reasoning_content,
                    force_reasoning_content=force_reasoning_content,
                )
                for m in messages
            ]
        )
        turn = provider.chat(oai_msgs, tools=[])
        text = (getattr(turn, "text", None) or "").strip()
        if not text:
            return SummaryResult(text="(summary empty)", is_error=True)
        return SummaryResult(text=text)
    except Exception as e:
        return SummaryResult(text=f"(summary failed: {e})", is_error=True)
