from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

Decision = Literal["allow", "ask", "deny"]


@dataclass(frozen=True)
class AgentProfile:
    name: str
    description: str
    system_prompt: str = ""
    max_steps: int | None = None
    model: str | None = None
    permission_overrides: dict[str, Decision] = field(default_factory=dict)
