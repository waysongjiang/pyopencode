from __future__ import annotations
from dataclasses import dataclass
from typing import Dict, Optional

from .base import Tool

@dataclass
class ToolRegistry:
    _tools: Dict[str, Tool] = None  # type: ignore

    def __post_init__(self):
        if self._tools is None:
            self._tools = {}

    def register(self, tool: Tool) -> None:
        name = tool.spec.name
        if name in self._tools:
            raise ValueError(f"Tool already registered: {name}")
        self._tools[name] = tool

    def get(self, name: str) -> Tool:
        if name not in self._tools:
            raise KeyError(f"Unknown tool: {name}")
        return self._tools[name]

    def get_optional(self, name: str) -> Optional[Tool]:
        """Return a tool if registered, otherwise None.

        Use this in agent loops to avoid crashing when the model hallucinates
        an unknown tool name.
        """
        return self._tools.get(name)
    
    def list_specs(self):
        return [t.spec for t in self._tools.values()]
