from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from .llm.openai_compat import OpenAICompatProvider
from .llm.factory import resolve_provider
from .session.store import SessionStore
from .tools.registry import ToolRegistry
from .tools.permissions import PermissionGate, PermissionConfig
from .tools.builtin import register_builtin_tools

from .mcp.bridge import register_mcp_servers

from .agents.registry import AgentRegistry
from .agents.models import AgentProfile
from .config.loader import load_behavior_config
from .rules.resolver import load_rules_bundle
from .events.store import EventStore

@dataclass
class AppContext:
    cwd: Path
    provider: OpenAICompatProvider
    tools: ToolRegistry
    permissions: PermissionGate
    session: SessionStore
    auto_approve: bool = False
    agent: AgentProfile | None = None
    rules_text: str | None = None
    behavior_config_path: Path | None = None
    mcp_clients: list = field(default_factory=list)  # MCPClient list
    events: EventStore | None = None
    trace: bool = False
    stream: bool = False
    config_path: Optional[Path] = None

    def close(self) -> None:
        """Best-effort cleanup for background resources (e.g., MCP server processes)."""
        try:
            for c in self.mcp_clients or []:
                try:
                    c.close()
                except Exception:
                    pass
        except Exception:
            pass

    @staticmethod
    def from_env(
        cwd: Path,
        session_id: str | None,
        provider: str | None,
        model: str | None,
        base_url: str | None,
        api_key: str | None,
        auto_approve: bool,
        deny_bash: bool,
        allow_edit: bool,
        agent_name: str | None = None,
        behavior_config: Path | None = None,
        trace: bool = False,
        stream: bool = False,
        config_path: Optional[Path] = None,
    ) -> "AppContext":

        if config_path:
            config_path = config_path.expanduser().resolve()

        provider_client = resolve_provider(
            provider=provider,
            model=model,
            base_url=base_url,
            api_key=api_key,
            yaml_path=config_path,
        )

        tools = ToolRegistry()
        register_builtin_tools(tools)

        # ---- Phase 2: behavior config + rules + agents ----
        behavior = load_behavior_config(cwd=cwd, explicit_path=behavior_config)
        agent_registry = AgentRegistry.from_defaults(behavior)
        agent: AgentProfile = agent_registry.get(agent_name or behavior.default_agent)
        rules_bundle = load_rules_bundle(cwd=cwd, behavior=behavior)

        # ---- Phase 3: MCP servers (optional) ----
        mcp_clients = []
        if behavior.mcp_servers:
            try:
                mcp_clients = register_mcp_servers(tools, list(behavior.mcp_servers.values()))
            except Exception:
                mcp_clients = []

        # Start with defaults, then apply behavior config, then agent overrides, then CLI overrides.
        perm_cfg = PermissionConfig.default_extended()
        perm_cfg.apply_behavior(behavior.permissions)
        perm_cfg.apply_agent_overrides(agent.permission_overrides)

        if deny_bash:
            perm_cfg.set("bash", "deny")
        if allow_edit:
            perm_cfg.set("edit", "allow")
        if auto_approve:
            # allow both edit and bash for unattended runs
            perm_cfg.set("edit", "allow")
            perm_cfg.set("bash", "allow")

        permissions = PermissionGate(config=perm_cfg, auto_approve=auto_approve)

        session = SessionStore.open(session_id=session_id)
        events = EventStore.open(session.session_id)

        return AppContext(
            cwd=cwd,
            provider=provider_client,
            tools=tools,
            permissions=permissions,
            session=session,
            auto_approve=auto_approve,
            agent=agent,
            rules_text=rules_bundle.combined_text,
            behavior_config_path=behavior.loaded_from,
            mcp_clients=mcp_clients,
            events=events,
            trace=trace,
            stream=stream,
            config_path=config_path,
        )
