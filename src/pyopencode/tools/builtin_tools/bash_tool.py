from __future__ import annotations
from dataclasses import dataclass
from typing import Any
import os
import shutil

from ..base import ToolSpec, ToolResult, ToolContext
from ...util.subprocess import run_cmd

@dataclass
class BashTool:
    spec: ToolSpec = ToolSpec(
        name="bash",
        description="Run a shell command in the working directory. Returns stdout/stderr and exit code.",
        permission_key="bash",
        parameters={
            "type": "object",
            "properties": {
                "command": {"type": "string", "description": "Shell command to run."},
                "timeout": {"type": "integer", "default": 120, "description": "Timeout seconds."},
            },
            "required": ["command"],
        },
    )

    def execute(self, ctx: ToolContext, args: dict[str, Any]) -> ToolResult:
        cmd = (args.get("command") or "").strip()
        timeout = int(args.get("timeout", 120))
        if not cmd:
            return ToolResult("Empty command.", is_error=True)

        # Use a real shell so built-ins like `cd`, pipes, &&, env expansion work.
        if os.name == "nt":
            # Windows: let cmd.exe parse builtins and operators
            parts = ["cmd.exe", "/c", cmd]
        else:
            # POSIX: prefer bash, fallback to sh
            shell = "bash" if shutil.which("bash") else "sh"
            parts = [shell, "-lc", cmd]

        res = run_cmd(parts, cwd=ctx.cwd, timeout=timeout)

        out = ""
        if res.stdout:
            out += f"STDOUT:\n{res.stdout}\n"
        if res.stderr:
            out += f"STDERR:\n{res.stderr}\n"
        out += f"EXIT_CODE: {res.returncode}"
        return ToolResult(out, is_error=(res.returncode != 0))
