from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any, Literal

Role = Literal["system", "user", "assistant", "tool"]

@dataclass
class Message:
    role: Role
    # content can be null in some OpenAI-compatible APIs when tool_calls are present
    content: str | None
    name: str | None = None
    tool_call_id: str | None = None
    # Assistant-only: OpenAI-compatible tool call representation
    tool_calls: list[dict[str, Any]] | None = None
    # DeepSeek thinking-with-tools compatibility
    reasoning_content: str | None = None

    def to_openai(self, *, include_reasoning_content: bool = False, force_reasoning_content: bool = False) -> dict[str, Any]:
        d: dict[str, Any] = {"role": self.role, "content": self.content}
        # "name" is not part of tool messages in many OpenAI-compatible APIs
        if self.name and self.role != "tool":
            d["name"] = self.name
        if self.tool_call_id:
            d["tool_call_id"] = self.tool_call_id
        if self.role == "assistant":
            if self.tool_calls is not None:
                d["tool_calls"] = self.tool_calls
            # DeepSeek (thinking mode) may require reasoning_content for all assistant messages
            if force_reasoning_content or (include_reasoning_content and self.tool_calls is not None):
                d["reasoning_content"] = self.reasoning_content or ""
        return d

@dataclass
class ToolCall:
    id: str
    name: str
    arguments: dict[str, Any]  # parsed json

@dataclass
class AssistantTurn:
    text: str = ""
    tool_calls: list[ToolCall] = field(default_factory=list)
    reasoning_content: str | None = None
