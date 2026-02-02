from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ..session.models import Message
from .policy import CompactionPolicy
from .summarizer import summarize


SUMMARY_NAME = "pyopencode_summary"
SKILL_NAME = "pyopencode_skill"
RULES_NAME = "pyopencode_rules"
AGENT_NAME = "pyopencode_agent"


@dataclass
class PromptBuildResult:
    messages: list[dict[str, Any]]
    # If non-empty, the caller may want to append this to the session.
    new_summary_message: Message | None = None


def maybe_load_skill(cwd: Path) -> str | None:
    p = (cwd / "SKILL.md").resolve()
    if not p.exists() or not p.is_file():
        return None
    try:
        return p.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return None


def build_prompt_messages(
    *,
    cwd: Path,
    session_messages: list[Message],
    provider,
    policy: CompactionPolicy,
    include_reasoning_content: bool,
    force_reasoning_content: bool = False,
    ensure_skill: bool = True,
    rules_text: str | None = None,
    agent_prompt: str | None = None,
) -> PromptBuildResult:
    """Build the message list sent to the LLM.

    - Ensures SKILL.md is injected (as a system message) if present.
    - Keeps only a rolling window of recent messages.
    - Optionally summarizes older content when conversations get long.
    """

    msgs = list(session_messages)
    new_summary: Message | None = None

    def _truncate_text(text: str, max_chars: int, *, marker: str = "... (truncated) ...") -> str:
        """Truncate long text by keeping head + tail.

        This keeps salient context (often errors are at the end) while preventing
        prompt blowups from huge pastes.
        """
        if max_chars <= 0 or len(text) <= max_chars:
            return text
        half = max(1, max_chars // 2)
        head = text[:half]
        tail = text[-half:]
        return head + "\n\n" + marker + "\n\n" + tail

    # Ensure skill prompt exists once.
    if ensure_skill:
        has_skill = any(m.role == "system" and m.name == SKILL_NAME for m in msgs)
        skill = maybe_load_skill(cwd)
        if skill and not has_skill:
            msgs.insert(0, Message(role="system", name=SKILL_NAME, content=f"Project SKILL.md:\n\n{skill}"))

    # Phase 2: inject Rules + Agent profile (non-persisted, always at the top).
    if rules_text and rules_text.strip():
        msgs.insert(0, Message(role="system", name=RULES_NAME, content=f"Rules:\n\n{rules_text.strip()}"))
    if agent_prompt and agent_prompt.strip():
        msgs.insert(0, Message(role="system", name=AGENT_NAME, content=agent_prompt.strip()))

    # Find latest summary message (acts as a logical cutoff).
    summary_idx = None
    for i in range(len(msgs) - 1, -1, -1):
        if msgs[i].role == "system" and msgs[i].name == SUMMARY_NAME:
            summary_idx = i
            break

    # If conversation is too long, summarize earlier part into a new summary.
    if len(msgs) >= policy.summarize_when_over:
        # Summarize everything except: the first system prompt(s) and the last max_messages window.
        tail = msgs[-policy.max_messages :]
        head = msgs[:-policy.max_messages]

        # Remove existing summary from head to avoid duplication.
        head_to_sum = [m for m in head if not (m.role == "system" and m.name == SUMMARY_NAME)]

        # Only summarize non-trivial chunks.
        if len(head_to_sum) >= 8:
            sres = summarize(provider, head_to_sum, include_reasoning_content=include_reasoning_content, force_reasoning_content=force_reasoning_content,)
            new_summary = Message(role="system", name=SUMMARY_NAME, content=sres.text)
            msgs = list(tail)
            # Prepend summary; skill injection happens below if enabled.
            msgs.insert(0, new_summary)

    # Hard cap: keep only last max_messages, but preserve system + last summary.
    if len(msgs) > policy.max_messages:
        kept_system: list[Message] = []
        kept_other: list[Message] = []
        for m in msgs:
            if m.role == "system":
                kept_system.append(m)
            else:
                kept_other.append(m)
        kept_other = kept_other[-(policy.max_messages - len(kept_system)) :]
        msgs = kept_system + kept_other

    # Final safety: truncate overly long message contents (including tool results from older sessions).
    safe_msgs: list[Message] = []
    for m in msgs:
        if m.content is None:
            safe_msgs.append(m)
            continue

        limit = policy.max_message_chars
        if m.role == "tool":
            limit = min(limit, policy.max_tool_result_chars)
        if len(m.content) > limit:
            safe_msgs.append(
                Message(
                    role=m.role,
                    name=m.name,
                    tool_call_id=m.tool_call_id,
                    tool_calls=m.tool_calls,
                    reasoning_content=m.reasoning_content,
                    content=_truncate_text(m.content, limit),
                )
            )
        else:
            safe_msgs.append(m)

    oai = [m.to_openai(include_reasoning_content=include_reasoning_content, force_reasoning_content=force_reasoning_content) for m in safe_msgs]
    return PromptBuildResult(messages=oai, new_summary_message=new_summary)
