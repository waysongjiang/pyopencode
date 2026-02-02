from __future__ import annotations

import json
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Any

from platformdirs import user_data_dir
from .models import Message

APP_NAME = "pyopencode"

def _sessions_dir() -> Path:
    root = Path(user_data_dir(APP_NAME))
    d = root / "sessions"
    d.mkdir(parents=True, exist_ok=True)
    return d

@dataclass
class SessionStore:
    session_id: str
    path: Path
    messages: list[Message]

    @staticmethod
    def open(session_id: str | None = None) -> "SessionStore":
        sid = session_id or uuid.uuid4().hex[:12]
        path = _sessions_dir() / f"{sid}.jsonl"
        msgs: list[Message] = []
        if path.exists():
            for line in path.read_text(encoding="utf-8").splitlines():
                if not line.strip():
                    continue
                try:
                    obj = json.loads(line)
                    msgs.append(Message(**obj))
                except Exception:
                    # Best-effort: ignore corrupted/partial trailing lines.
                    # This can happen if the process was terminated mid-write.
                    continue
        return SessionStore(session_id=sid, path=path, messages=msgs)

    def append(self, msg: Message) -> None:
        self.messages.append(msg)
        # Crash-safety: append + flush + fsync so that resume logic can reliably
        # detect persisted assistant tool calls.
        with self.path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(msg.__dict__, ensure_ascii=False) + "\n")
            f.flush()
            try:
                import os

                os.fsync(f.fileno())
            except Exception:
                # Best-effort: some filesystems may not support fsync.
                pass

    def extend(self, msgs: Iterable[Message]) -> None:
        for m in msgs:
            self.append(m)

    def to_openai_messages(self, *, include_reasoning_content: bool = False) -> list[dict[str, Any]]:
        return [m.to_openai(include_reasoning_content=include_reasoning_content) for m in self.messages]
