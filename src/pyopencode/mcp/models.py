from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any

@dataclass
class MCPServerConfig:
    name: str
    command: list[str]
    env: dict[str, str] = field(default_factory=dict)
    cwd: str | None = None
    prefix: str | None = None  # tool name prefix override

    @staticmethod
    def from_obj(name: str, obj: Any) -> "MCPServerConfig | None":
        if not isinstance(obj, dict):
            return None
        cmd = obj.get("command")
        if not isinstance(cmd, list) or not all(isinstance(x, str) for x in cmd):
            return None
        env = obj.get("env", {})
        if not isinstance(env, dict):
            env = {}
        cwd = obj.get("cwd")
        if cwd is not None and not isinstance(cwd, str):
            cwd = None
        prefix = obj.get("prefix")
        if prefix is not None and not isinstance(prefix, str):
            prefix = None
        return MCPServerConfig(
            name=name,
            command=[str(x) for x in cmd],
            env={str(k): str(v) for k, v in env.items()},
            cwd=cwd,
            prefix=prefix,
        )
