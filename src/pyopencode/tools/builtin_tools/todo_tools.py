from __future__ import annotations

import json
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

from platformdirs import user_data_dir

from ..base import ToolContext, ToolResult, ToolSpec


Status = Literal["todo", "doing", "done"]


@dataclass
class TodoItem:
    id: str
    text: str
    status: Status = "todo"
    created_at: float = 0.0
    updated_at: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "text": self.text,
            "status": self.status,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }

    @staticmethod
    def from_dict(d: dict[str, Any]) -> "TodoItem":
        return TodoItem(
            id=str(d.get("id") or ""),
            text=str(d.get("text") or ""),
            status=d.get("status") or "todo",
            created_at=float(d.get("created_at") or 0.0),
            updated_at=float(d.get("updated_at") or 0.0),
        )


def _todo_path(session_id: str | None) -> Path:
    root = Path(user_data_dir("pyopencode")) / "todos"
    root.mkdir(parents=True, exist_ok=True)
    sid = session_id or "default"
    return root / f"{sid}.json"


def _load(session_id: str | None) -> list[TodoItem]:
    p = _todo_path(session_id)
    if not p.exists():
        return []
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
        if not isinstance(data, list):
            return []
        return [TodoItem.from_dict(x) for x in data if isinstance(x, dict)]
    except Exception:
        return []


def _save(session_id: str | None, items: list[TodoItem]) -> None:
    p = _todo_path(session_id)
    p.write_text(json.dumps([i.to_dict() for i in items], ensure_ascii=False, indent=2), encoding="utf-8")


def _format(items: list[TodoItem]) -> str:
    if not items:
        return "(empty todo list)"
    lines = []
    for it in items:
        lines.append(f"- [{it.status}] {it.id}: {it.text}")
    return "\n".join(lines)


class TodoReadTool:
    spec = ToolSpec(
        name="todoread",
        description="Read the current todo list for this session.",
        parameters={"type": "object", "properties": {}},
        permission_key="read",
    )

    def execute(self, ctx: ToolContext, args: dict[str, Any]) -> ToolResult:
        items = _load(ctx.session_id)
        return ToolResult(content=_format(items))


class TodoWriteTool:
    spec = ToolSpec(
        name="todowrite",
        description=(
            "Update the todo list for this session. Supports add/update/remove/clear. "
            "Use todoread to view current items."
        ),
        parameters={
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": ["add", "update", "remove", "clear"],
                    "description": "Operation to perform.",
                },
                "text": {"type": "string", "description": "Todo text (for add/update)."},
                "id": {"type": "string", "description": "Todo id (for update/remove)."},
                "status": {
                    "type": "string",
                    "enum": ["todo", "doing", "done"],
                    "description": "New status (for update).",
                },
            },
            "required": ["action"],
        },
        permission_key="edit",
    )

    def execute(self, ctx: ToolContext, args: dict[str, Any]) -> ToolResult:
        action = str(args.get("action") or "").strip().lower()
        items = _load(ctx.session_id)
        now = time.time()

        if action == "clear":
            items = []
            _save(ctx.session_id, items)
            return ToolResult(content="Cleared todo list.\n" + _format(items))

        if action == "add":
            text = str(args.get("text") or "").strip()
            if not text:
                return ToolResult(content="todowrite add requires: text", is_error=True)
            it = TodoItem(id=uuid.uuid4().hex[:8], text=text, status="todo", created_at=now, updated_at=now)
            items.append(it)
            _save(ctx.session_id, items)
            return ToolResult(content="Added todo.\n" + _format(items))

        if action in {"update", "remove"}:
            tid = str(args.get("id") or "").strip()
            if not tid:
                return ToolResult(content=f"todowrite {action} requires: id", is_error=True)
            idx = next((i for i, x in enumerate(items) if x.id == tid), None)
            if idx is None:
                return ToolResult(content=f"Todo id not found: {tid}", is_error=True)

            if action == "remove":
                removed = items.pop(idx)
                _save(ctx.session_id, items)
                return ToolResult(content=f"Removed todo {removed.id}.\n" + _format(items))

            # update
            text = args.get("text")
            status = args.get("status")
            if text is not None:
                items[idx].text = str(text)
            if status is not None:
                st = str(status)
                if st not in {"todo", "doing", "done"}:
                    return ToolResult(content=f"Invalid status: {st}", is_error=True)
                items[idx].status = st  # type: ignore
            items[idx].updated_at = now
            _save(ctx.session_id, items)
            return ToolResult(content=f"Updated todo {items[idx].id}.\n" + _format(items))

        return ToolResult(content=f"Invalid action: {action}", is_error=True)
