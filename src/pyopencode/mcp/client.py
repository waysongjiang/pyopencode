from __future__ import annotations

import json
import subprocess
import threading
import itertools
from dataclasses import dataclass
from typing import Any

from ..tools.base import ToolResult

@dataclass
class MCPToolInfo:
    name: str
    description: str
    input_schema: dict[str, Any]

class MCPClient:
    """A minimal JSON-RPC client for MCP-like servers over stdio.

    Expected methods:
      - tools/list -> { tools: [{name, description, inputSchema}] }
      - tools/call -> tool invocation; returns a "content" field or arbitrary json
    """

    def __init__(self, command: list[str], *, cwd: str | None = None, env: dict[str, str] | None = None):
        self._proc = subprocess.Popen(
            command,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,
            cwd=cwd,
            env={**(env or {})} if env else None,
        )
        if self._proc.stdin is None or self._proc.stdout is None:
            raise RuntimeError("Failed to start MCP server process with pipes.")
        self._stdin = self._proc.stdin
        self._stdout = self._proc.stdout
        self._id_iter = itertools.count(1)
        self._lock = threading.Lock()
        self._pending: dict[int, tuple[threading.Event, dict[str, Any]]] = {}
        self._reader = threading.Thread(target=self._read_loop, daemon=True)
        self._reader.start()

    def close(self):
        try:
            if self._proc.poll() is None:
                self._proc.terminate()
        except Exception:
            pass

    def _read_loop(self):
        for line in self._stdout:
            line = line.strip()
            if not line:
                continue
            try:
                msg = json.loads(line)
            except Exception:
                continue
            if isinstance(msg, dict) and "id" in msg:
                try:
                    mid = int(msg["id"])
                except Exception:
                    continue
                with self._lock:
                    if mid in self._pending:
                        ev, holder = self._pending[mid]
                        holder["msg"] = msg
                        ev.set()

    def request(self, method: str, params: dict[str, Any] | None = None, timeout: float = 30.0) -> Any:
        rid = next(self._id_iter)
        req = {"jsonrpc": "2.0", "id": rid, "method": method, "params": params or {}}
        ev = threading.Event()
        holder: dict[str, Any] = {}
        with self._lock:
            self._pending[rid] = (ev, holder)
            self._stdin.write(json.dumps(req, ensure_ascii=False) + "\n")
            self._stdin.flush()
        ok = ev.wait(timeout)
        with self._lock:
            self._pending.pop(rid, None)
        if not ok:
            raise TimeoutError(f"MCP request timeout: {method}")
        msg = holder.get("msg", {})
        if "error" in msg:
            raise RuntimeError(str(msg["error"]))
        return msg.get("result")

    def list_tools(self) -> list[MCPToolInfo]:
        res = self.request("tools/list", {})
        tools = []
        if isinstance(res, dict):
            arr = res.get("tools", [])
        else:
            arr = res
        if isinstance(arr, list):
            for t in arr:
                if not isinstance(t, dict):
                    continue
                name = t.get("name")
                desc = t.get("description", "")
                schema = t.get("inputSchema") or t.get("input_schema") or t.get("parameters") or {}
                if isinstance(name, str):
                    tools.append(MCPToolInfo(name=name, description=str(desc), input_schema=schema if isinstance(schema, dict) else {}))
        return tools

    def call_tool(self, name: str, arguments: dict[str, Any]) -> ToolResult:
        res = self.request("tools/call", {"name": name, "arguments": arguments or {}})
        # normalize content
        try:
            if isinstance(res, dict):
                if "content" in res:
                    c = res["content"]
                    if isinstance(c, str):
                        return ToolResult(content=c, is_error=False)
                    if isinstance(c, list):
                        texts = []
                        for part in c:
                            if isinstance(part, dict):
                                if part.get("type") == "text":
                                    texts.append(str(part.get("text","")))
                                else:
                                    texts.append(json.dumps(part, ensure_ascii=False))
                            else:
                                texts.append(str(part))
                        return ToolResult(content="\n".join(texts), is_error=False)
                # fallback
                return ToolResult(content=json.dumps(res, ensure_ascii=False, indent=2), is_error=False)
            if isinstance(res, str):
                return ToolResult(content=res, is_error=False)
            return ToolResult(content=json.dumps(res, ensure_ascii=False, indent=2), is_error=False)
        except Exception as e:
            return ToolResult(content=f"MCP tool call parse error: {e}", is_error=True)
