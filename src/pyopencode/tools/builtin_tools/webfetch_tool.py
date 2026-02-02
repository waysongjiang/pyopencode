from __future__ import annotations

import re
import urllib.request
from html.parser import HTMLParser
from typing import Any

from ..base import ToolContext, ToolResult, ToolSpec


class _HTMLTextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self._parts: list[str] = []
        self._skip_depth = 0

    def handle_starttag(self, tag: str, attrs):  # type: ignore[override]
        if tag.lower() in {"script", "style", "noscript"}:
            self._skip_depth += 1

    def handle_endtag(self, tag: str):  # type: ignore[override]
        if tag.lower() in {"script", "style", "noscript"} and self._skip_depth > 0:
            self._skip_depth -= 1

    def handle_data(self, data: str):  # type: ignore[override]
        if self._skip_depth > 0:
            return
        text = data.strip()
        if text:
            self._parts.append(text)

    def text(self) -> str:
        joined = "\n".join(self._parts)
        # collapse excessive blank lines
        joined = re.sub(r"\n{3,}", "\n\n", joined)
        return joined.strip()


class WebFetchTool:
    """Fetch a URL and return readable text.

    Designed for local usage without extra dependencies (requests/bs4).
    """

    spec = ToolSpec(
        name="webfetch",
        description="Fetch a URL and return its text content (HTML will be converted to plain text).",
        parameters={
            "type": "object",
            "properties": {
                "url": {"type": "string", "description": "The URL to fetch."},
                "timeout": {"type": "integer", "description": "Timeout seconds (default 15)."},
                "max_chars": {
                    "type": "integer",
                    "description": "Max characters to return (default 12000).",
                },
                "headers": {
                    "type": "object",
                    "description": "Optional HTTP headers.",
                    "additionalProperties": {"type": "string"},
                },
            },
            "required": ["url"],
        },
        permission_key="read",
    )

    def execute(self, ctx: ToolContext, args: dict[str, Any]) -> ToolResult:
        url = str(args.get("url") or "").strip()
        if not url:
            return ToolResult(content="Missing required field: url", is_error=True)

        timeout = int(args.get("timeout") or 15)
        max_chars = int(args.get("max_chars") or 12000)
        headers = args.get("headers") or {}
        if not isinstance(headers, dict):
            headers = {}

        req = urllib.request.Request(url, headers={"User-Agent": "pyopencode/0.1", **headers})
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                raw = resp.read()
                content_type = (resp.headers.get("Content-Type") or "").lower()
        except Exception as e:
            return ToolResult(content=f"webfetch failed: {e}", is_error=True)

        # Best-effort decode
        text = None
        for enc in ("utf-8", "utf-8-sig", "latin-1"):
            try:
                text = raw.decode(enc)
                break
            except Exception:
                continue
        if text is None:
            return ToolResult(content="webfetch failed: could not decode response body", is_error=True)

        if "html" in content_type or "<html" in text.lower():
            parser = _HTMLTextExtractor()
            try:
                parser.feed(text)
                text = parser.text()
            except Exception:
                # fall back to raw
                pass

        if len(text) > max_chars:
            head = text[: max_chars // 2]
            tail = text[-max_chars // 2 :]
            text = head + "\n\n... (truncated) ...\n\n" + tail

        return ToolResult(content=text)
