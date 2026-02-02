
from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ..base import ToolSpec, ToolResult, ToolContext
from ...util.fs import resolve_path, FsError

@dataclass
class WriteFileTool:
    spec: ToolSpec = ToolSpec(
        name="write",
        description="Create or overwrite a file with given content.",
        permission_key="edit",
        parameters={
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "File path relative to cwd."},
                "content": {"type": "string", "description": "Full file content."},
                "mkdirs": {"type": "boolean", "default": True, "description": "Create parent directories if needed."},
            },
            "required": ["path", "content"],
        },
    )

    def execute(self, ctx: ToolContext, args: dict[str, Any]) -> ToolResult:
        cwd = Path(ctx.cwd)
        path = args["path"]
        content = args["content"]
        mkdirs = bool(args.get("mkdirs", True))
        try:
            p = resolve_path(cwd, path)
        except FsError as e:
            return ToolResult(str(e), is_error=True)
        if mkdirs:
            p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8")
        return ToolResult(f"Wrote {path} ({len(content)} chars).")
