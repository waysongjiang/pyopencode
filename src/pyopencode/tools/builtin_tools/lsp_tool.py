from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ..base import ToolContext, ToolResult, ToolSpec
from ...util.fs import resolve_path, read_text


def _as_int(v: Any, default: int) -> int:
    try:
        return int(v)
    except Exception:
        return default


@dataclass
class LspTool:
    """Phase 4: lightweight code navigation.

    This is intentionally local-first and dependency-light.
    For Python files, it uses Jedi (installed via pyproject.toml).
    """

    spec: ToolSpec = ToolSpec(
        name="lsp",
        description=(
            "Lightweight local code navigation for supported languages. "
            "Actions: definition, references, hover, symbols, diagnostics. "
            "For Python (.py), uses Jedi."
        ),
        parameters={
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": ["definition", "references", "hover", "symbols", "diagnostics"],
                    "description": "Navigation action.",
                },
                "path": {"type": "string", "description": "File path (relative to cwd)."},
                "line": {"type": "integer", "description": "1-based line number."},
                "column": {"type": "integer", "description": "0-based column offset."},
                "query": {
                    "type": "string",
                    "description": "Optional symbol substring filter for symbols action.",
                },
                "limit": {"type": "integer", "description": "Max results (default 50)."},
            },
            "required": ["action", "path"],
        },
        permission_key="read",
    )

    def execute(self, ctx: ToolContext, args: dict[str, Any]) -> ToolResult:
        action = (args.get("action") or "").strip().lower()
        path_str = (args.get("path") or "").strip()
        if not action or not path_str:
            return ToolResult(content="Missing required args: action, path", is_error=True)

        cwd = Path(ctx.cwd)
        try:
            path = resolve_path(cwd, path_str)
        except Exception as e:
            return ToolResult(content=f"Invalid path: {e}", is_error=True)
        if not path.exists():
            return ToolResult(content=f"File not found: {path_str}", is_error=True)

        # Only Python supported out-of-the-box.
        if path.suffix.lower() != ".py":
            return ToolResult(
                content=(
                    "LSP tool currently supports Python (.py) out-of-the-box. "
                    "For other languages, consider wiring an external MCP/LSP server in Phase 5."
                ),
                is_error=True,
            )

        code = read_text(path)
        line = _as_int(args.get("line"), 1)
        column = _as_int(args.get("column"), 0)
        limit = max(1, min(_as_int(args.get("limit"), 50), 200))
        query = (args.get("query") or "").strip().lower()

        try:
            import jedi  # type: ignore
        except Exception as e:
            return ToolResult(content=f"Missing dependency jedi: {e}", is_error=True)

        try:
            script = jedi.Script(code=code, path=str(path))
            results: list[dict[str, Any]] = []

            if action == "symbols":
                names = script.get_names(all_scopes=True, definitions=True, references=False)
                for n in names:
                    nm = (n.name or "")
                    if query and query not in nm.lower():
                        continue
                    results.append(
                        {
                            "name": nm,
                            "type": getattr(n, "type", None),
                            "line": getattr(n, "line", None),
                            "column": getattr(n, "column", None),
                            "module_path": str(path),
                        }
                    )
                    if len(results) >= limit:
                        break



            elif action == "diagnostics":
                diags = []
                # Syntax diagnostics (fast path)
                try:
                    compile(code, str(path), "exec")
                except SyntaxError as se:
                    diags.append({
                        "severity": "error",
                        "source": "python.compile",
                        "message": str(se),
                        "line": getattr(se, "lineno", None),
                        "column": getattr(se, "offset", None),
                    })

                # Bytecode compilation (best-effort)
                try:
                    import subprocess, sys
                    cp = subprocess.run(
                        [sys.executable, "-m", "py_compile", str(path)],
                        capture_output=True,
                        text=True,
                        cwd=str(cwd),
                        timeout=20,
                    )
                    if cp.returncode != 0:
                        msg = (cp.stderr or cp.stdout or "").strip()
                        if msg:
                            diags.append({
                                "severity": "error",
                                "source": "py_compile",
                                "message": msg[:4000],
                            })
                except Exception as e:
                    diags.append({
                        "severity": "warning",
                        "source": "py_compile",
                        "message": f"py_compile failed: {e}",
                    })

                return ToolResult(
                    content=json.dumps({"ok": True, "diagnostics": diags}, ensure_ascii=False, indent=2)
                )
            elif action == "definition":
                defs = script.goto(line=line, column=column, follow_imports=True, follow_builtin_imports=False)
                for d in defs[:limit]:
                    mp = d.module_path or str(path)
                    results.append(
                        {
                            "name": d.name,
                            "type": d.type,
                            "module_path": str(mp),
                            "line": d.line,
                            "column": d.column,
                            "description": (d.description or "")[:400],
                        }
                    )

            elif action == "references":
                refs = script.get_references(
                    line=line,
                    column=column,
                    include_builtins=False,
                )
                for r in refs[:limit]:
                    mp = r.module_path or str(path)
                    results.append(
                        {
                            "name": r.name,
                            "type": r.type,
                            "module_path": str(mp),
                            "line": r.line,
                            "column": r.column,
                            "is_definition": bool(getattr(r, "is_definition", lambda: False)()),
                        }
                    )

            elif action == "hover":
                defs = script.goto(line=line, column=column, follow_imports=True, follow_builtin_imports=False)
                d0 = defs[0] if defs else None
                if not d0:
                    return ToolResult(content=json.dumps({"ok": True, "hover": ""}, ensure_ascii=False))
                hover = (d0.docstring(raw=True) or "")
                # Keep hover reasonably sized.
                if len(hover) > 6000:
                    hover = hover[:6000] + "\n... (truncated)"
                return ToolResult(
                    content=json.dumps(
                        {
                            "ok": True,
                            "name": d0.name,
                            "type": d0.type,
                            "module_path": str(d0.module_path or path),
                            "line": d0.line,
                            "column": d0.column,
                            "hover": hover,
                        },
                        ensure_ascii=False,
                        indent=2,
                    )
                )

            else:
                return ToolResult(content=f"Unknown action: {action}", is_error=True)

            return ToolResult(content=json.dumps({"ok": True, "results": results}, ensure_ascii=False, indent=2))

        except Exception as e:
            return ToolResult(content=f"LSP error: {e}", is_error=True)
