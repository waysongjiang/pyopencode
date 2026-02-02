from __future__ import annotations

from dataclasses import dataclass, field
from fnmatch import fnmatch
from typing import Any, Literal

from rich.console import Console

Decision = Literal["allow", "ask", "deny"]

console = Console()


@dataclass
class PermissionRule:
    """A single permission rule.

    match supports:
    - "tool:<name_or_pattern>"  -> matches tool name only
    - otherwise: fnmatch against both permission_key and tool_name
    """

    match: str
    decision: Decision

    @staticmethod
    def from_obj(obj: Any) -> "PermissionRule | None":
        if not isinstance(obj, dict):
            return None
        m = obj.get("match")
        d = obj.get("decision")
        if not isinstance(m, str) or d not in {"allow", "ask", "deny"}:
            return None
        return PermissionRule(match=m, decision=d)


@dataclass
class PermissionConfig:
    """Phase 2 permission config.

    Backwards compatible with Phase 0/1 (read/edit/bash fields), but also supports
    arbitrary tool keys and rule-based matching.
    """

    defaults: dict[str, Decision] = field(default_factory=lambda: {"read": "allow", "edit": "ask", "bash": "ask", "mcp": "ask",})
    rules: list[PermissionRule] = field(default_factory=list)

    @staticmethod
    def default_extended() -> "PermissionConfig":
        return PermissionConfig()

    def set(self, key: str, decision: Decision) -> None:
        self.defaults[key] = decision

    def apply_behavior(self, rules: list[PermissionRule]) -> None:
        # behavior rules appended after defaults; later rules win.
        self.rules.extend(rules)

    def apply_agent_overrides(self, overrides: dict[str, Decision]) -> None:
        for k, v in overrides.items():
            self.defaults[k] = v

    def _match_rules(self, permission_key: str, tool_name: str) -> Decision | None:
        decision: Decision | None = None
        for rule in self.rules:
            m = rule.match
            if m.startswith("tool:"):
                pat = m[len("tool:") :]
                if fnmatch(tool_name, pat):
                    decision = rule.decision
            else:
                if fnmatch(permission_key, m) or fnmatch(tool_name, m):
                    decision = rule.decision
        return decision

    def decide(self, permission_key: str, tool_name: str) -> Decision:
        r = self._match_rules(permission_key, tool_name)
        if r is not None:
            return r
        return self.defaults.get(permission_key, self.defaults.get(tool_name, "ask"))


class PermissionGate:
    def __init__(self, config: PermissionConfig, auto_approve: bool = False):
        self.config = config
        self.auto_approve = auto_approve

    def decide(self, permission_key: str, tool_name: str, args_preview: str) -> bool:
        decision = self.config.decide(permission_key, tool_name)
        if decision == "allow":
            return True
        if decision == "deny":
            console.print(f"[red]Denied[/red] tool {tool_name} ({permission_key})")
            return False

        # ask
        if self.auto_approve:
            return True

        console.print(f"\n[yellow]Tool requires approval[/yellow]: [bold]{tool_name}[/bold]\n{args_preview}")
        resp = console.input("Approve? [y/N] ").strip().lower()
        return resp in {"y", "yes"}
