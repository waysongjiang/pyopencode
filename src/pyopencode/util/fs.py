from __future__ import annotations
from pathlib import Path

class FsError(RuntimeError):
    pass

def resolve_path(cwd: Path, path_str: str) -> Path:
    p = Path(path_str)
    if not p.is_absolute():
        p = (cwd / p).resolve()
    else:
        p = p.resolve()
    # Ensure within cwd to avoid escapes? For local agent, safer default.
    try:
        p.relative_to(cwd.resolve())
    except Exception:
        raise FsError(f"Path escapes working directory: {path_str}")
    return p

def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")
