
from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
from typing import Any
import glob as _glob

from ..base import ToolSpec, ToolResult, ToolContext

@dataclass
class GlobTool:
    spec: ToolSpec = ToolSpec(
        name="glob",
        description="Find files matching a glob pattern (relative to cwd).",
        permission_key="read",
        parameters={
            "type": "object",
            "properties": {
                "pattern": {"type": "string", "description": "Glob pattern, e.g. 'src/**/*.py'."},
                "max_results": {"type": "integer", "default": 200},
            },
            "required": ["pattern"],
        },
    )

    def execute(self, ctx: ToolContext, args: dict[str, Any]) -> ToolResult:
        cwd = Path(ctx.cwd)
        pattern = args["pattern"]
        max_results = int(args.get("max_results", 200))
        full = str((cwd / pattern))
        matches = _glob.glob(full, recursive=True)
        rel = []
        for m in matches:
            try:
                rel.append(str(Path(m).resolve().relative_to(cwd.resolve())))
            except Exception:
                continue
            if len(rel) >= max_results:
                break
        return ToolResult("\n".join(rel) if rel else "(no matches)")
