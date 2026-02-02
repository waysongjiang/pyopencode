from __future__ import annotations

import json
import os
import urllib.request
import urllib.error
from dataclasses import dataclass
from typing import Any, Callable, Iterator

from ..session.models import AssistantTurn, ToolCall

@dataclass
class OpenAICompatProvider:
    """
    Minimal OpenAI-compatible Chat Completions client.
    Works with OpenAI and many compatible gateways (OpenRouter, vLLM, LM Studio, etc.)
    """
    model: str
    base_url: str
    api_key: str
    provider_name: str = "openai"  # openai|deepseek|kimi|qwen
    def chat(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        *,
        stream: bool = False,
        on_token: Callable[[str], None] | None = None,
    ) -> AssistantTurn:
        if not self.api_key:
            raise RuntimeError(
                "Missing API key. Set PYOPENCODE_API_KEY (or --api-key), "
                "or provider-specific envs like OPENAI_API_KEY / DEEPSEEK_API_KEY / MOONSHOT_API_KEY / QWEN_API_KEY."
            )

        url = self.base_url.rstrip("/") + "/chat/completions"
        payload: dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "temperature": 0.2,
        }
        if stream:
            payload["stream"] = True
        if tools:
            payload["tools"] = tools
            payload["tool_choice"] = "auto"

        data = json.dumps(payload).encode("utf-8")
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}",
        }
        req = urllib.request.Request(url, data=data, headers=headers, method="POST")
        try:
            if not stream:
                with urllib.request.urlopen(req, timeout=120) as resp:
                    raw = resp.read().decode("utf-8", errors="replace")
                obj = json.loads(raw)
                choice = obj["choices"][0]
                msg = choice["message"]

                turn = AssistantTurn(
                    text=msg.get("content") or "",
                    reasoning_content=msg.get("reasoning_content"),
                )
                tool_calls = msg.get("tool_calls") or []
                for tc in tool_calls:
                    fn = tc.get("function", {})
                    name = fn.get("name")
                    arg_str = fn.get("arguments") or "{}"
                    try:
                        args = json.loads(arg_str) if isinstance(arg_str, str) else (arg_str or {})
                    except json.JSONDecodeError:
                        # best-effort: empty args
                        args = {}
                    turn.tool_calls.append(ToolCall(id=tc.get("id", ""), name=name, arguments=args))
                return turn

            # --- Streaming mode ---
            # OpenAI-compatible servers stream SSE lines of the form:
            #   data: {"choices":[{"delta":{...}}]}
            # ending with:
            #   data: [DONE]
            text_parts: list[str] = []
            reasoning_parts: list[str] = []
            # tool_calls are streamed as deltas by index; accumulate into strings.
            tc_by_index: dict[int, dict[str, Any]] = {}

            def _handle_delta(delta: dict[str, Any]) -> None:
                if "content" in delta and delta["content"]:
                    chunk = str(delta["content"])
                    text_parts.append(chunk)
                    if on_token:
                        on_token(chunk)
                # Some providers stream reasoning separately.
                if "reasoning_content" in delta and delta["reasoning_content"]:
                    reasoning_parts.append(str(delta["reasoning_content"]))
                if "tool_calls" in delta and delta["tool_calls"]:
                    for tc in delta["tool_calls"]:
                        idx = int(tc.get("index", 0))
                        cur = tc_by_index.setdefault(idx, {"id": "", "name": "", "arguments": ""})
                        if tc.get("id"):
                            cur["id"] = tc.get("id")
                        fn = tc.get("function") or {}
                        if fn.get("name"):
                            cur["name"] = fn.get("name")
                        if fn.get("arguments"):
                            cur["arguments"] += str(fn.get("arguments"))

            with urllib.request.urlopen(req, timeout=120) as resp:
                for raw_line in resp:
                    try:
                        line = raw_line.decode("utf-8", errors="replace").strip()
                    except Exception:
                        continue
                    if not line:
                        continue
                    if not line.startswith("data:"):
                        continue
                    data_str = line[len("data:"):].strip()
                    if data_str == "[DONE]":
                        break
                    try:
                        ev = json.loads(data_str)
                    except Exception:
                        continue
                    choices = ev.get("choices") or []
                    if not choices:
                        continue
                    delta = (choices[0].get("delta") or {})
                    _handle_delta(delta)

            turn = AssistantTurn(
                text="".join(text_parts),
                reasoning_content="".join(reasoning_parts) if reasoning_parts else None,
            )
            for idx in sorted(tc_by_index.keys()):
                tc = tc_by_index[idx]
                arg_str = tc.get("arguments") or "{}"
                try:
                    args = json.loads(arg_str) if isinstance(arg_str, str) else (arg_str or {})
                except json.JSONDecodeError:
                    args = {}
                turn.tool_calls.append(ToolCall(id=str(tc.get("id") or ""), name=str(tc.get("name") or ""), arguments=args))
            return turn
        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8", errors="replace") if hasattr(e, "read") else ""
            raise RuntimeError(f"Provider HTTPError {e.code}: {e.reason}\n{body}")
        except urllib.error.URLError as e:
            raise RuntimeError(f"Provider URLError: {e}")
