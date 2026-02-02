from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from platformdirs import user_config_dir

from .models import CommandSpec

APP_NAME = "pyopencode"

def _command_dirs(cwd: Path) -> list[Path]:
    # project-first
    return [
        cwd / ".pyopencode" / "commands",
        cwd / ".opencode" / "commands",
        cwd / "commands",
    ]

def _global_command_dirs() -> list[Path]:
    return [Path(user_config_dir(APP_NAME)) / "commands"]

def _parse_frontmatter(text: str) -> tuple[dict[str, str], str]:
    """Parse a minimal frontmatter.

    Format:
    ---
    key: value
    key2: value2
    ---
    body...
    """
    lines = text.splitlines()
    if len(lines) >= 3 and lines[0].strip() == "---":
        meta: dict[str, str] = {}
        i = 1
        while i < len(lines):
            if lines[i].strip() == "---":
                body = "\n".join(lines[i+1:])
                return meta, body
            line = lines[i]
            if ":" in line:
                k, v = line.split(":", 1)
                meta[k.strip()] = v.strip()
            i += 1
    return {}, text

def _load_command_file(path: Path) -> CommandSpec | None:
    try:
        text = path.read_text(encoding="utf-8")
    except Exception:
        return None
    meta, body = _parse_frontmatter(text)
    name = path.stem
    desc = meta.get("description", "")
    agent = meta.get("agent")
    model = meta.get("model")
    ms = meta.get("max_steps")
    max_steps: int | None = None
    if ms:
        try:
            max_steps = int(ms)
        except Exception:
            max_steps = None
    spec = CommandSpec(
        name=name,
        description=desc,
        agent=agent if agent else None,
        prompt=body.strip(),
        source_path=path,
        model=model if model else None,
        max_steps=max_steps,
    )
    return spec

def discover_commands(*, cwd: Path, inline: dict[str, CommandSpec] | None = None) -> dict[str, CommandSpec]:
    """Discover available commands.

    Merge order: global dirs < project dirs < inline (from behavior config).
    Later sources override earlier ones by name.
    """
    out: dict[str, CommandSpec] = {}

    for d in _global_command_dirs():
        if d.exists() and d.is_dir():
            for p in sorted(d.glob("*.md")) + sorted(d.glob("*.txt")):
                spec = _load_command_file(p)
                if spec:
                    out[spec.name] = spec

    for d in _command_dirs(cwd):
        if d.exists() and d.is_dir():
            for p in sorted(d.glob("*.md")) + sorted(d.glob("*.txt")):
                spec = _load_command_file(p)
                if spec:
                    out[spec.name] = spec

    if inline:
        for k, v in inline.items():
            out[k] = v

    return out

def load_command(*, cwd: Path, name: str, inline: dict[str, CommandSpec] | None = None) -> CommandSpec:
    cmds = discover_commands(cwd=cwd, inline=inline)
    if name not in cmds:
        raise KeyError(f"Unknown command: {name}. Available: {', '.join(sorted(cmds.keys()))}")
    return cmds[name]

def render_command_prompt(spec: CommandSpec, args: dict[str, str]) -> str:
    """Render prompt template by replacing {{key}} placeholders."""
    text = spec.prompt
    for k, v in args.items():
        text = text.replace("{{" + k + "}}", v)
    # Any unreplaced placeholders remain; that's fine.
    return text
