
from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
from typing import Any
import re

from ..base import ToolSpec, ToolResult, ToolContext
from ...util.fs import resolve_path, read_text, FsError

@dataclass
class GrepTool:
    spec: ToolSpec = ToolSpec(
        name="grep",
        description="Search for a pattern in files. Returns matching lines with line numbers.",
        permission_key="read",
        parameters={
            "type": "object",
            "properties": {
                "pattern": {"type": "string", "description": "Regex (default) or literal string if regex=false."},
                "path": {"type": "string", "description": "File or directory to search (relative to cwd). Default '.'"},
                "regex": {"type": "boolean", "default": True},
                "include": {"type": "string", "description": "Optional glob filter like '*.py'."},
                "max_matches": {"type": "integer", "default": 200},
            },
            "required": ["pattern"],
        },
    )

    def execute(self, ctx: ToolContext, args: dict[str, Any]) -> ToolResult:
        cwd = Path(ctx.cwd).expanduser().resolve()
        pattern = args["pattern"]
        path = args.get("path", ".")
        is_regex = bool(args.get("regex", True))
        include = args.get("include")
        max_matches = int(args.get("max_matches", 200))

        try:
            target = resolve_path(cwd, path)
        except FsError as e:
            return ToolResult(str(e), is_error=True)
        if not target.exists():
            return ToolResult(f"Path not found: {path}", is_error=True)

        file_list: list[Path] = []
        if target.is_file():
            file_list = [target]
        else:
            # walk
            for p in target.rglob("*"):
                if not p.is_file():
                    continue
                if include and not p.match(include):
                    continue
                file_list.append(p)

        rx = None
        if is_regex:
            try:
                rx = re.compile(pattern)
            except re.error as e:
                return ToolResult(f"Invalid regex: {e}", is_error=True)

        out_lines = []
        count = 0
        for f in file_list:
            try:
                text = read_text(f)
            except Exception:
                continue
            for i, line in enumerate(text.splitlines(), start=1):
                hit = (rx.search(line) is not None) if rx else (pattern in line)
                if hit:
                    rel = str(f.resolve().relative_to(cwd))
                    out_lines.append(f"{rel}:{i}: {line}")
                    count += 1
                    if count >= max_matches:
                        return ToolResult("\n".join(out_lines))
        return ToolResult("\n".join(out_lines) if out_lines else "(no matches)")
