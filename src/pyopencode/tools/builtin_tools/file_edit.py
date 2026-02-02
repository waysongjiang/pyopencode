
from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ..base import ToolSpec, ToolResult, ToolContext
from ...util.fs import resolve_path, read_text, FsError

@dataclass
class EditFileTool:
    spec: ToolSpec = ToolSpec(
        name="edit",
        description="Replace a line range in a file. Lines are 1-based inclusive. This is deterministic and safe.",
        permission_key="edit",
        parameters={
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "File path relative to cwd."},
                "start_line": {"type": "integer", "description": "1-based start line (inclusive)."},
                "end_line": {"type": "integer", "description": "1-based end line (inclusive)."},
                "new_text": {"type": "string", "description": "Replacement text for the range."},
            },
            "required": ["path", "start_line", "end_line", "new_text"],
        },
    )

    def execute(self, ctx: ToolContext, args: dict[str, Any]) -> ToolResult:
        cwd = Path(ctx.cwd)
        path = args["path"]
        start = int(args["start_line"])
        end = int(args["end_line"])
        new_text = args["new_text"]

        try:
            p = resolve_path(cwd, path)
        except FsError as e:
            return ToolResult(str(e), is_error=True)
        if not p.exists() or not p.is_file():
            return ToolResult(f"File not found: {path}", is_error=True)

        text = read_text(p)
        lines = text.splitlines()
        if start < 1 or end < start or start > len(lines) + 1:
            return ToolResult(f"Invalid line range {start}-{end} for file with {len(lines)} lines.", is_error=True)
        # allow end == len(lines)+1 as append at EOF (treat as empty replacement at end)
        end = min(end, len(lines))

        before = lines[:start-1]
        after = lines[end:]
        new_lines = new_text.splitlines()
        merged = before + new_lines + after
        p.write_text("\n".join(merged) + ("\n" if text.endswith("\n") else ""), encoding="utf-8")
        return ToolResult(f"Edited {path}: replaced lines {start}-{end}.")
