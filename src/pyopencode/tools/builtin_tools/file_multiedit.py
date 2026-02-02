
from __future__ import annotations
from dataclasses import dataclass
from typing import Any

from ..base import ToolSpec, ToolResult, ToolContext
from .file_edit import EditFileTool

@dataclass
class MultiEditFileTool:
    spec: ToolSpec = ToolSpec(
        name="multiedit",
        description="Apply multiple line-range edits in a single call. Edits must be non-overlapping and sorted.",
        permission_key="edit",
        parameters={
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "File path relative to cwd."},
                "edits": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "start_line": {"type": "integer"},
                            "end_line": {"type": "integer"},
                            "new_text": {"type": "string"},
                        },
                        "required": ["start_line", "end_line", "new_text"],
                    },
                },
            },
            "required": ["path", "edits"],
        },
    )

    def execute(self, ctx: ToolContext, args: dict[str, Any]) -> ToolResult:
        path = args["path"]
        edits = args["edits"]
        if not isinstance(edits, list) or not edits:
            return ToolResult("edits must be a non-empty list", is_error=True)
        # validate ordering
        ranges = [(int(e["start_line"]), int(e["end_line"])) for e in edits]
        if ranges != sorted(ranges, key=lambda x: x[0]):
            return ToolResult("edits must be sorted by start_line", is_error=True)
        for (s1, e1), (s2, e2) in zip(ranges, ranges[1:]):
            if s2 <= e1:
                return ToolResult("edits must not overlap", is_error=True)

        # apply from bottom to top to keep line numbers stable
        editor = EditFileTool()
        for e in reversed(edits):
            res = editor.execute(ctx, {"path": path, **e})
            if res.is_error:
                return res
        return ToolResult(f"Applied {len(edits)} edits to {path}.")
