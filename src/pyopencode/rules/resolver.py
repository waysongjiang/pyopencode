from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from platformdirs import user_config_dir

from ..config.models import BehaviorConfig

APP_NAME = "pyopencode"


@dataclass(frozen=True)
class RuleDoc:
    scope: str  # "global" or "project" or "extra"
    path: Path
    content: str


@dataclass(frozen=True)
class RuleBundle:
    docs: list[RuleDoc]
    combined_text: str


def _read_text(p: Path) -> str | None:
    try:
        if p.exists() and p.is_file():
            return p.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return None
    return None


def _project_rule_candidates(cwd: Path) -> list[Path]:
    return [
        cwd / "AGENTS.md",
        cwd / "RULES.md",
        cwd / ".opencode" / "AGENTS.md",
        cwd / ".opencode" / "RULES.md",
    ]


def _global_rule_candidates() -> list[Path]:
    d = Path(user_config_dir(APP_NAME))
    return [
        d / "AGENTS.md",
        d / "RULES.md",
    ]


def load_rules_bundle(*, cwd: Path, behavior: BehaviorConfig | None = None) -> RuleBundle:
    docs: list[RuleDoc] = []

    # global
    for p in _global_rule_candidates():
        txt = _read_text(p)
        if txt:
            docs.append(RuleDoc(scope="global", path=p, content=txt))
            break

    # project
    for p in _project_rule_candidates(cwd):
        txt = _read_text(p)
        if txt:
            docs.append(RuleDoc(scope="project", path=p, content=txt))
            break

    # extra files from config
    if behavior is not None:
        for p in behavior.extra_rule_files:
            txt = _read_text(p)
            if txt:
                docs.append(RuleDoc(scope="extra", path=p, content=txt))

    combined = _combine_rules(docs)
    return RuleBundle(docs=docs, combined_text=combined)


def _combine_rules(docs: Iterable[RuleDoc]) -> str:
    parts: list[str] = []
    for d in docs:
        header = f"[{d.scope}] {d.path}"
        parts.append(header)
        parts.append("-" * len(header))
        parts.append(d.content.strip())
        parts.append("")
    return "\n".join(parts).strip()
