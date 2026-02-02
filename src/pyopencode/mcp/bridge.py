from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .models import MCPServerConfig
from .client import MCPClient
from ..tools.registry import ToolRegistry
from ..tools.base import ToolSpec, Tool, ToolContext, ToolResult

@dataclass
class MCPTool(Tool):
    spec: ToolSpec
    client: MCPClient
    remote_name: str

    def execute(self, ctx: ToolContext, args: dict[str, Any]) -> ToolResult:
        return self.client.call_tool(self.remote_name, args)

def register_mcp_servers(registry: ToolRegistry, servers: list[MCPServerConfig]) -> list[MCPClient]:
    clients: list[MCPClient] = []
    for s in servers:
        client = MCPClient(s.command, cwd=s.cwd, env=s.env)
        clients.append(client)
        prefix = s.prefix or f"mcp.{s.name}"
        for t in client.list_tools():
            tool_name = f"{prefix}.{t.name}"
            spec = ToolSpec(
                name=tool_name,
                description=f"[MCP:{s.name}] {t.description}".strip(),
                parameters=t.input_schema if isinstance(t.input_schema, dict) else {},
                permission_key="mcp",
            )
            registry.register(MCPTool(spec=spec, client=client, remote_name=t.name))
    return clients
