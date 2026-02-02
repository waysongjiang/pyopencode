from __future__ import annotations

import json
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

from platformdirs import user_data_dir

APP_NAME = "pyopencode"


def _events_dir() -> Path:
    root = Path(user_data_dir(APP_NAME))
    d = root / "events"
    d.mkdir(parents=True, exist_ok=True)
    return d


@dataclass
class Event:
    ts: float
    type: str
    data: dict[str, Any]


@dataclass
class EventStore:
    """Simple jsonl event store per session.

    This is intentionally append-only and tolerant of partial corruption.
    """

    session_id: str
    path: Path

    @staticmethod
    def open(session_id: str) -> "EventStore":
        path = _events_dir() / f"{session_id}.jsonl"
        return EventStore(session_id=session_id, path=path)

    def append(self, event_type: str, data: dict[str, Any]) -> None:
        ev = Event(ts=time.time(), type=event_type, data=data)
        with self.path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(ev.__dict__, ensure_ascii=False) + "\n")

    def iter_events(self) -> Iterable[Event]:
        if not self.path.exists():
            return []
        out: list[Event] = []
        for line in self.path.read_text(encoding="utf-8", errors="replace").splitlines():
            if not line.strip():
                continue
            try:
                obj = json.loads(line)
                out.append(Event(ts=float(obj.get("ts", 0.0)), type=str(obj.get("type")), data=obj.get("data") or {}))
            except Exception:
                continue
        return out
