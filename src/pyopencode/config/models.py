from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from ..tools.permissions import PermissionRule
from ..commands.models import CommandSpec
from ..mcp.models import MCPServerConfig


@dataclass
class AgentConfig:
    name: str
    description: str = ""
    system_prompt: str = ""
    max_steps: int | None = None
    model: str | None = None
    permission_overrides: dict[str, str] = field(default_factory=dict)

    @staticmethod
    def from_obj(name: str, obj: Any) -> "AgentConfig | None":
        if not isinstance(obj, dict):
            return None
        desc = obj.get("description", "")
        sp = obj.get("system_prompt", "")
        ms = obj.get("max_steps")
        model = obj.get("model")
        perms = obj.get("permission_overrides", {})
        if not isinstance(desc, str) or not isinstance(sp, str):
            return None
        if ms is not None and not isinstance(ms, int):
            return None
        if model is not None and not isinstance(model, str):
            return None
        if not isinstance(perms, dict):
            perms = {}
        return AgentConfig(
            name=name,
            description=desc,
            system_prompt=sp,
            max_steps=ms,
            model=model,
            permission_overrides={str(k): str(v) for k, v in perms.items()},
        )


@dataclass
class BehaviorConfig:
    """Behavior config loaded from JSON.

    Phase 2: agents/rules/permissions
    Phase 3: commands + MCP servers
    """

    default_agent: str = "general"
    permissions: list[PermissionRule] = field(default_factory=list)
    agents: dict[str, AgentConfig] = field(default_factory=dict)
    extra_rule_files: list[Path] = field(default_factory=list)

    # Phase 3
    commands: dict[str, CommandSpec] = field(default_factory=dict)
    mcp_servers: dict[str, MCPServerConfig] = field(default_factory=dict)

    loaded_from: Path | None = None
