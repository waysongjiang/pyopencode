from __future__ import annotations

import json
import sys
import time

TOOLS = [
    {
        "name": "echo",
        "description": "Echo back the provided text.",
        "inputSchema": {
            "type": "object",
            "properties": {"text": {"type": "string"}},
            "required": ["text"],
        },
    },
    {
        "name": "now",
        "description": "Return current epoch time.",
        "inputSchema": {"type": "object", "properties": {}, "required": []},
    },
]

def _reply(rid: int, result=None, error=None):
    msg = {"jsonrpc": "2.0", "id": rid}
    if error is not None:
        msg["error"] = {"message": str(error)}
    else:
        msg["result"] = result
    sys.stdout.write(json.dumps(msg, ensure_ascii=False) + "\n")
    sys.stdout.flush()

def main():
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            req = json.loads(line)
        except Exception:
            continue
        if not isinstance(req, dict):
            continue
        rid = req.get("id")
        method = req.get("method")
        params = req.get("params") or {}
        try:
            rid_int = int(rid)
        except Exception:
            continue

        try:
            if method == "tools/list":
                _reply(rid_int, {"tools": TOOLS})
            elif method == "tools/call":
                name = params.get("name")
                args = params.get("arguments") or {}
                if name == "echo":
                    _reply(rid_int, {"content": [{"type": "text", "text": str(args.get("text",""))}]})
                elif name == "now":
                    _reply(rid_int, {"content": [{"type": "text", "text": str(time.time())}]})
                else:
                    _reply(rid_int, error=f"Unknown tool: {name}")
            else:
                _reply(rid_int, error=f"Unknown method: {method}")
        except Exception as e:
            _reply(rid_int, error=e)

if __name__ == "__main__":
    main()
