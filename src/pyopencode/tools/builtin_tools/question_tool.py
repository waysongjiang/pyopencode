from __future__ import annotations

import json
from typing import Any

from rich.console import Console
from rich.prompt import Prompt

from ..base import ToolContext, ToolResult, ToolSpec


console = Console()


class QuestionTool:
    spec = ToolSpec(
        name="question",
        description=(
            "Ask the user a clarifying question during REPL/tool execution. "
            "Useful when the assistant needs a choice or a missing parameter."
        ),
        parameters={
            "type": "object",
            "properties": {
                "question": {"type": "string", "description": "Question to ask the user."},
                "choices": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Optional list of choices. User will pick by number or text.",
                },
                "default": {"type": "string", "description": "Default answer (optional)."},
            },
            "required": ["question"],
        },
        permission_key="read",
    )

    def execute(self, ctx: ToolContext, args: dict[str, Any]) -> ToolResult:
        q = str(args.get("question") or "").strip()
        if not q:
            return ToolResult(content="Missing required field: question", is_error=True)

        choices = args.get("choices")
        if choices is not None and not isinstance(choices, list):
            choices = None
        choices = [str(x) for x in (choices or [])]
        default = args.get("default")
        default = str(default) if default is not None else None

        if choices:
            console.print("\n[bold]Question:[/bold] " + q)
            for i, c in enumerate(choices, start=1):
                console.print(f"  {i}. {c}")
            ans = Prompt.ask("Your answer (number or text)", default=default)
            ans = ans.strip()
            picked = ans
            if ans.isdigit():
                idx = int(ans)
                if 1 <= idx <= len(choices):
                    picked = choices[idx - 1]
            payload = {"answer": picked, "raw": ans, "choices": choices}
            return ToolResult(content=json.dumps(payload, ensure_ascii=False))

        ans = Prompt.ask("\n" + q, default=default)
        payload = {"answer": ans}
        return ToolResult(content=json.dumps(payload, ensure_ascii=False))
