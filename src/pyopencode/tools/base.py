from __future__ import annotations
from dataclasses import dataclass
from typing import Any, Callable, Protocol

@dataclass(frozen=True)
class ToolSpec:
    name: str
    description: str
    parameters: dict[str, Any]   # JSONSchema
    permission_key: str          # "read" | "edit" | "bash"

class Tool(Protocol):
    spec: ToolSpec
    def execute(self, ctx: "ToolContext", args: dict[str, Any]) -> "ToolResult": ...

@dataclass
class ToolResult:
    content: str
    is_error: bool = False

@dataclass
class ToolContext:
    cwd: str
    # Optional session id for tools that want to persist state (todo, etc.)
    session_id: str | None = None
