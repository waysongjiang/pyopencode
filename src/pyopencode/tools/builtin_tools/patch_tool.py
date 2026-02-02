
from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
from typing import Any
import tempfile
import os
import shutil

from ..base import ToolSpec, ToolResult, ToolContext
from ...util.subprocess import run_cmd

@dataclass
class PatchTool:
    spec: ToolSpec = ToolSpec(
        name="patch",
        description="Apply a unified diff patch to the working directory. Uses git apply if available, else system patch.",
        permission_key="edit",
        parameters={
            "type": "object",
            "properties": {
                "diff": {"type": "string", "description": "Unified diff text."},
            },
            "required": ["diff"],
        },
    )

    def execute(self, ctx: ToolContext, args: dict[str, Any]) -> ToolResult:
        diff_text = args["diff"]
        cwd = ctx.cwd
        with tempfile.NamedTemporaryFile("w", delete=False, suffix=".patch", encoding="utf-8") as f:
            f.write(diff_text)
            patch_path = f.name

        try:
            # prefer git apply if git exists
            git = shutil.which("git")
            if git:
                res = run_cmd([git, "apply", "--whitespace=nowarn", patch_path], cwd=cwd, timeout=120)
                if res.returncode == 0:
                    return ToolResult("Patch applied with git apply.")
                # fall back to patch
            patch = shutil.which("patch")
            if patch:
                res2 = run_cmd([patch, "-p0", "-i", patch_path], cwd=cwd, timeout=120)
                if res2.returncode == 0:
                    return ToolResult("Patch applied with patch.")
                return ToolResult(f"Failed to apply patch.\n(git) rc={res.returncode if git else 'n/a'} stderr={res.stderr if git else ''}\n(patch) rc={res2.returncode} stderr={res2.stderr}", is_error=True)
            return ToolResult("No patch tool available (need git or patch).", is_error=True)
        finally:
            try:
                os.unlink(patch_path)
            except Exception:
                pass
