from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from platformdirs import user_config_dir

from .models import BehaviorConfig, AgentConfig
from ..commands.models import CommandSpec
from ..mcp.models import MCPServerConfig
from ..tools.permissions import PermissionRule

APP_NAME = "pyopencode"


def _candidate_paths(cwd: Path) -> list[Path]:
    # project-level (higher priority)
    return [
        cwd / ".pyopencode.json",
        cwd / "pyopencode.json",
        cwd / ".opencode.json",
        cwd / "opencode.json",
    ]


def _global_candidate_paths() -> list[Path]:
    cfg_dir = Path(user_config_dir(APP_NAME))
    return [
        cfg_dir / "pyopencode.json",
        cfg_dir / "opencode.json",
    ]


def _load_json(p: Path) -> dict[str, Any] | None:
    try:
        obj = json.loads(p.read_text(encoding="utf-8"))
        if isinstance(obj, dict):
            return obj
        return None
    except Exception:
        return None


def _merge_dicts(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    out = dict(base)
    for k, v in override.items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _merge_dicts(out[k], v)  # type: ignore
        else:
            out[k] = v
    return out


def load_behavior_config(*, cwd: Path, explicit_path: Path | None = None) -> BehaviorConfig:
    """Load behavior config.

    Merge order: global < project < explicit_path.
    """
    merged: dict[str, Any] = {}
    loaded_from: Path | None = None

    for p in _global_candidate_paths():
        if p.exists() and p.is_file():
            obj = _load_json(p)
            if obj is not None:
                merged = _merge_dicts(merged, obj)
                loaded_from = p

    for p in _candidate_paths(cwd):
        if p.exists() and p.is_file():
            obj = _load_json(p)
            if obj is not None:
                merged = _merge_dicts(merged, obj)
                loaded_from = p
                break  # first match wins for project-level

    if explicit_path is not None:
        p = explicit_path.expanduser().resolve()
        if p.exists() and p.is_file():
            obj = _load_json(p)
            if obj is not None:
                merged = _merge_dicts(merged, obj)
                loaded_from = p

    cfg = BehaviorConfig()
    cfg.loaded_from = loaded_from

    # default_agent
    da = merged.get("default_agent")
    if isinstance(da, str) and da.strip():
        cfg.default_agent = da.strip()

    # permissions
    perms = merged.get("permissions", [])
    if isinstance(perms, list):
        for it in perms:
            r = PermissionRule.from_obj(it)
            if r is not None:
                cfg.permissions.append(r)

    # agents
    agents = merged.get("agents", {})
    if isinstance(agents, dict):
        for name, obj in agents.items():
            if not isinstance(name, str):
                continue
            ac = AgentConfig.from_obj(name, obj)
            if ac is not None:
                cfg.agents[name] = ac

    # commands (inline)
    cmds = merged.get("commands", {})
    if isinstance(cmds, dict):
        for name, obj in cmds.items():
            if not isinstance(name, str):
                continue
            cs = CommandSpec.from_obj(name, obj)
            if cs is not None:
                cfg.commands[name] = cs

    # mcp servers
    mcp = merged.get("mcp_servers", {}) or merged.get("mcpServers", {})
    if isinstance(mcp, dict):
        for name, obj in mcp.items():
            if not isinstance(name, str):
                continue
            sc = MCPServerConfig.from_obj(name, obj)
            if sc is not None:
                cfg.mcp_servers[name] = sc

    # extra rules files
    rf = merged.get("rules_files", [])
    if isinstance(rf, list):
        for f in rf:
            if isinstance(f, str) and f.strip():
                p = (cwd / f).expanduser()
                try:
                    cfg.extra_rule_files.append(p.resolve())
                except Exception:
                    cfg.extra_rule_files.append(p)

    return cfg
