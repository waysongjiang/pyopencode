from __future__ import annotations

from pathlib import Path
from typing import Any

from ..base import ToolContext, ToolResult, ToolSpec


class SkillTool:
    spec = ToolSpec(
        name="skill",
        description=(
            "Load a SKILL.md (or any markdown file) and return its contents so the assistant can follow it. "
            "If no path is provided, defaults to ./SKILL.md under the working directory."
        ),
        parameters={
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Path to the skill markdown file (default: SKILL.md)."},
                "max_chars": {"type": "integer", "description": "Max characters to return (default 20000)."},
            },
        },
        permission_key="read",
    )

    def execute(self, ctx: ToolContext, args: dict[str, Any]) -> ToolResult:
        rel = str(args.get("path") or "SKILL.md")
        max_chars = int(args.get("max_chars") or 20000)
        base = Path(ctx.cwd)
        p = (base / rel).resolve()
        try:
            # Prevent escaping the project directory
            if base not in p.parents and p != base:
                return ToolResult(content=f"Skill path escapes cwd: {p}", is_error=True)
            if not p.exists() or not p.is_file():
                return ToolResult(content=f"Skill file not found: {p}", is_error=True)
            text = p.read_text(encoding="utf-8", errors="replace")
        except Exception as e:
            return ToolResult(content=f"skill failed: {e}", is_error=True)

        if len(text) > max_chars:
            text = text[: max_chars] + "\n\n... (truncated) ..."
        return ToolResult(content=text)
