from __future__ import annotations
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ..base import ToolSpec, ToolResult, ToolContext
from ...util.fs import resolve_path, FsError

@dataclass
class ListDirTool:
    spec: ToolSpec = ToolSpec(
        name="list",
        description="List files/directories under a path (relative to cwd).",
        permission_key="read",
        parameters={
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Directory path relative to cwd. Default '.'"},
                "max_entries": {"type": "integer", "description": "Max entries to return", "default": 200},
                "recursive": {"type": "boolean", "description": "If true, list recursively", "default": False},
            },
            "required": [],
        },
    )

    def execute(self, ctx: ToolContext, args: dict[str, Any]) -> ToolResult:
        cwd = Path(ctx.cwd).expanduser().resolve()
        path = args.get("path", ".")
        max_entries = int(args.get("max_entries", 200))
        recursive = bool(args.get("recursive", False))
        try:
            p = resolve_path(cwd, path)
        except FsError as e:
            return ToolResult(str(e), is_error=True)
        if not p.exists():
            return ToolResult(f"Path not found: {path}", is_error=True)
        if not p.is_dir():
            return ToolResult(f"Not a directory: {path}", is_error=True)

        entries = []
        if recursive:
            for root, dirs, files in os.walk(p):
                rootp = Path(root)
                for d in dirs:
                    entries.append(str((rootp / d).resolve().relative_to(cwd)))
                    if len(entries) >= max_entries:
                        break
                for f in files:
                    entries.append(str((rootp / f).resolve().relative_to(cwd)))
                    if len(entries) >= max_entries:
                        break
                if len(entries) >= max_entries:
                    break
        else:
            for child in sorted(p.iterdir(), key=lambda x: (not x.is_dir(), x.name.lower())):
                entries.append(str(child.resolve().relative_to(cwd)))
                if len(entries) >= max_entries:
                    break

        out = "\n".join(entries) if entries else "(empty)"
        return ToolResult(out)
