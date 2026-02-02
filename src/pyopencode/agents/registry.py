from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from ..config.models import BehaviorConfig
from .models import AgentProfile, Decision


def _as_decision(v: str) -> Decision | None:
    v = v.lower().strip()
    if v in {"allow", "ask", "deny"}:
        return v  # type: ignore
    return None


def _default_agents() -> list[AgentProfile]:
    # Keep prompts short; rules/skill will be injected separately.
    base = "You are a local coding agent. Use tools to read files and run commands; don't fabricate outputs."

    return [
        AgentProfile(
            name="general",
            description="General assistant (balanced).",
            system_prompt=base,
            permission_overrides={},
        ),
        AgentProfile(
            name="plan",
            description="Read-only planning: produce a step-by-step plan without editing or running commands.",
            system_prompt=base
            + "\n\nMode: PLAN ONLY. Do not call edit/write/patch/bash. If needed, ask the user for confirmation to switch to build/run.",
            permission_overrides={"edit": "deny", "bash": "deny"},
        ),
        AgentProfile(
            name="explore",
            description="Read-only exploration: inspect repository, locate relevant code, summarize findings.",
            system_prompt=base
            + "\n\nMode: EXPLORE. Prefer list/glob/grep/read. Do not edit files or run bash unless explicitly allowed.",
            permission_overrides={"edit": "deny", "bash": "deny"},
        ),
        AgentProfile(
            name="build",
            description="Implement changes (edit/patch allowed) but avoid running shell commands unless necessary.",
            system_prompt=base
            + "\n\nMode: BUILD. You may edit files when necessary. Prefer deterministic edits (edit/multiedit/patch). Use bash only when explicitly required.",
            permission_overrides={"edit": "allow", "bash": "ask"},
        ),
        AgentProfile(
            name="run",
            description="Execute tests/build steps (bash allowed) and implement fixes.",
            system_prompt=base
            + "\n\nMode: RUN. You may use bash to run tests and commands. Be safe: show the exact command; avoid destructive actions.",
            permission_overrides={"edit": "allow", "bash": "allow"},
        ),
    ]


@dataclass
class AgentRegistry:
    _agents: dict[str, AgentProfile]
    default_agent: str = "general"

    @staticmethod
    def from_defaults(behavior: BehaviorConfig | None = None) -> "AgentRegistry":
        agents = {a.name: a for a in _default_agents()}
        default_agent = "general"

        if behavior is not None:
            if behavior.default_agent:
                default_agent = behavior.default_agent
            # merge custom agents from config
            for name, ac in behavior.agents.items():
                overrides: dict[str, Decision] = {}
                for k, v in ac.permission_overrides.items():
                    dv = _as_decision(v)
                    if dv is not None:
                        overrides[k] = dv
                agents[name] = AgentProfile(
                    name=name,
                    description=ac.description or f"Custom agent: {name}",
                    system_prompt=ac.system_prompt or "",
                    max_steps=ac.max_steps,
                    model=ac.model,
                    permission_overrides=overrides,
                )

        return AgentRegistry(_agents=agents, default_agent=default_agent)

    def names(self) -> list[str]:
        return sorted(self._agents.keys())

    def get(self, name: str) -> AgentProfile:
        if name in self._agents:
            return self._agents[name]
        # fallback
        return self._agents.get(self.default_agent, self._agents["general"])
