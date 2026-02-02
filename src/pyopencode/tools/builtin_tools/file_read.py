
from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ..base import ToolSpec, ToolResult, ToolContext
from ...util.fs import resolve_path, read_text, FsError

@dataclass
class ReadFileTool:
    spec: ToolSpec = ToolSpec(
        name="read",
        description="Read a text file. Optionally limit to a line range.",
        permission_key="read",
        parameters={
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "File path relative to cwd."},
                "start_line": {"type": "integer", "description": "1-based start line (inclusive)."},
                "end_line": {"type": "integer", "description": "1-based end line (inclusive)."},
                "max_chars": {"type": "integer", "default": 40000},
            },
            "required": ["path"],
        },
    )

    def execute(self, ctx: ToolContext, args: dict[str, Any]) -> ToolResult:
        cwd = Path(ctx.cwd)
        path = args["path"]
        try:
            p = resolve_path(cwd, path)
        except FsError as e:
            return ToolResult(str(e), is_error=True)
        if not p.exists() or not p.is_file():
            return ToolResult(f"File not found: {path}", is_error=True)

        text = read_text(p)
        lines = text.splitlines()

        s = args.get("start_line")
        e = args.get("end_line")
        if s is not None or e is not None:
            s = int(s or 1)
            e = int(e or len(lines))
            s = max(1, s)
            e = min(len(lines), e)
            excerpt = lines[s-1:e]
        else:
            excerpt = lines

        out = "\n".join(excerpt)
        max_chars = int(args.get("max_chars", 40000))
        if len(out) > max_chars:
            out = out[:max_chars] + "\n... (truncated)"
        return ToolResult(out)
