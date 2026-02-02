from __future__ import annotations

import json
import uuid
import time

from rich.console import Console
from rich.panel import Panel
from rich.align import Align

from .app_context import AppContext
from .session.models import Message
from .session.models import ToolCall
from .tools.base import ToolContext
from .tools.base import ToolResult
from .util.ordinal_suffix import ordinal
from .compaction.policy import CompactionPolicy
from .compaction.builder import build_prompt_messages

console = Console()

SYSTEM_PROMPT = """You are pyopencode, a local coding agent.
Rules:
- Use the provided tools to inspect files and run commands when needed.
- Prefer: list/glob/grep/read before editing files.
- When editing files, use deterministic line-range edits (edit/multiedit) or patch.
- Do not fabricate file contents or command outputs: use tools.
- Keep tool arguments minimal and correct.
"""


def _tool_specs_to_openai(tools_registry) -> list[dict]:
    out = []
    for spec in tools_registry.list_specs():
        out.append({
            "type": "function",
            "function": {
                "name": spec.name,
                "description": spec.description,
                "parameters": spec.parameters,
            },
        })
    return out


def _args_preview(args: dict) -> str:
    try:
        s = json.dumps(args, ensure_ascii=False, indent=2)
    except Exception:
        s = str(args)
    if len(s) > 2000:
        s = s[:2000] + "\n... (truncated)"
    return s


def _prompt_char_count(messages: list[dict]) -> int:
    total = 0
    for m in messages:
        c = m.get("content")
        if isinstance(c, str):
            total += len(c)
        rc = m.get("reasoning_content")
        if isinstance(rc, str):
            total += len(rc)
        tc = m.get("tool_calls")
        if tc:
            try:
                total += len(json.dumps(tc, ensure_ascii=False))
            except Exception:
                pass
    return total


def _parse_openai_tool_calls(tool_calls: list[dict] | None) -> list[ToolCall]:
    out: list[ToolCall] = []
    for tc in (tool_calls or []):
        try:
            fn = (tc.get("function") or {})
            name = fn.get("name")
            arg_str = fn.get("arguments") or "{}"
            args = json.loads(arg_str) if isinstance(arg_str, str) else (arg_str or {})
            out.append(ToolCall(id=str(tc.get("id") or ""), name=str(name or ""), arguments=args))
        except Exception:
            continue
    return out


# =========================
# 🔒 NEW: clean invalid tool messages from persisted sessions
# =========================
def _clean_invalid_tool_messages(ctx: AppContext) -> int:
    """Remove any tool messages that are not immediately preceded by an assistant message with tool_calls.
    Returns number of removed messages.
    """
    msgs = ctx.session.messages
    cleaned: list[Message] = []
    removed = 0
    for m in msgs:
        if m.role == "tool":
            if not cleaned:
                removed += 1
                continue
            prev = cleaned[-1]
            if prev.role != "assistant" or not prev.tool_calls:
                removed += 1
                continue
        cleaned.append(m)

    if removed:
        ctx.session.messages = cleaned
        if ctx.events:
            ctx.events.append(
                "session.cleaned_invalid_tool_messages",
                {"removed": removed, "kept": len(cleaned)},
            )
    return removed


# =========================
# 🔒 NEW: validate outgoing OpenAI-style messages
# =========================
def _validate_openai_messages(messages: list[dict]) -> None:
    """Validate OpenAI/DeepSeek tool-calling protocol:
    - A tool message must be immediately preceded by an assistant message with tool_calls.
    - Tool message should have tool_call_id.
    """
    for i, m in enumerate(messages):
        role = m.get("role")
        if role == "tool":
            if i == 0:
                raise RuntimeError("Invalid messages: tool message at index 0")
            prev = messages[i - 1]
            if prev.get("role") != "assistant" or not prev.get("tool_calls"):
                raise RuntimeError(
                    f"Invalid messages: tool message at index {i} has no preceding assistant tool_calls"
                )
            if not m.get("tool_call_id"):
                # some providers might tolerate, but safest to enforce
                raise RuntimeError(
                    f"Invalid messages: tool message at index {i} missing tool_call_id"
                )

def _clean_invalid_tool_dict_messages(messages: list[dict]) -> list[dict]:
    cleaned = []
    for m in messages:
        if m.get("role") == "tool":
            if not cleaned:
                continue
            prev = cleaned[-1]
            if prev.get("role") != "assistant" or not prev.get("tool_calls"):
                continue
        cleaned.append(m)
    return cleaned

# =========================
# 🔒 NEW: protocol safety check before appending a tool result to session
# =========================
def _assert_can_append_tool(ctx: AppContext, tool_call_id: str | None) -> None:
    if not ctx.session.messages:
        raise RuntimeError("Protocol violation: session empty before tool append")

    last = ctx.session.messages[-1]
    if last.role != "assistant" or not last.tool_calls:
        raise RuntimeError("Protocol violation: tool message without preceding assistant tool_calls")

    if not tool_call_id:
        raise RuntimeError("Protocol violation: tool message missing tool_call_id")


def _resume_pending_tool_calls(ctx: AppContext) -> bool:
    """Best-effort crash recovery.

    If a run crashed after persisting an assistant message that includes tool_calls,
    but before all tool results were appended, we can resume by executing the missing
    tool calls and appending corresponding tool messages.

    ✅ Safety: we only append tool messages if they will be contiguous after the assistant(tool_calls).
    """
    msgs = ctx.session.messages
    if not msgs:
        return False

    # Find the most recent assistant message that contains tool_calls.
    last_idx = -1
    for i in range(len(msgs) - 1, -1, -1):
        m = msgs[i]
        if m.role == "assistant" and m.tool_calls:
            last_idx = i
            break
        # If we hit a user message, stop scanning: pending tool calls must be after that.
        if m.role == "user":
            break
    if last_idx < 0:
        return False

    assistant = msgs[last_idx]
    tool_calls = _parse_openai_tool_calls(assistant.tool_calls)
    if not tool_calls:
        return False

    # Collect tool_call_ids already answered immediately after the assistant message.
    answered: set[str] = set()
    for j in range(last_idx + 1, len(msgs)):
        mj = msgs[j]
        if mj.role != "tool":
            break
        if mj.tool_call_id:
            answered.add(mj.tool_call_id)

    pending = [tc for tc in tool_calls if tc.id and tc.id not in answered]
    if not pending:
        return False

    # ✅ Safety: only resume if there are no non-tool messages between assistant and end,
    # except already appended contiguous tool messages.
    # That is: msgs[last_idx+1 : ] must be all tool messages.
    for j in range(last_idx + 1, len(msgs)):
        if msgs[j].role != "tool":
            # If anything else appears, refuse to resume to avoid illegal ordering.
            if ctx.events:
                ctx.events.append(
                    "resume.aborted_non_tool_after_assistant",
                    {"assistant_index": last_idx, "found_role": msgs[j].role, "found_index": j},
                )
            return False

    if ctx.events:
        ctx.events.append(
            "resume.pending_tools",
            {"count": len(pending), "assistant_index": last_idx, "tool_call_ids": [tc.id for tc in pending]},
        )

    # Execute missing tool calls sequentially.
    for tc in pending:
        tool = ctx.tools.get_optional(tc.name)
        if tool is None:
            # still need to answer the call to keep protocol consistent
            denied_msg = f"Tool {tc.name} not found (resume)."
            _assert_can_append_tool(ctx, tc.id)
            ctx.session.append(Message(role="tool", content=denied_msg, tool_call_id=tc.id))
            continue

        args = tc.arguments or {}
        preview = _args_preview(args)

        allowed = ctx.permissions.decide(tool.spec.permission_key, tool.spec.name, preview)
        if not allowed:
            denied_msg = f"Tool {tool.spec.name} was denied by user permissions (resume)."
            _assert_can_append_tool(ctx, tc.id)
            ctx.session.append(Message(role="tool", content=denied_msg, tool_call_id=tc.id))
            continue

        tctx = ToolContext(cwd=str(ctx.cwd), session_id=ctx.session.session_id)
        t0 = time.perf_counter()
        try:
            res: ToolResult = tool.execute(tctx, args)
        except Exception as e:
            res = ToolResult(content=f"Tool {tool.spec.name} exception: {e}", is_error=True)
        tool_elapsed_ms = int((time.perf_counter() - t0) * 1000)

        if ctx.events:
            ctx.events.append(
                "resume.tool_result",
                {
                    "tool": tool.spec.name,
                    "tool_call_id": tc.id,
                    "is_error": bool(res.is_error),
                    "elapsed_ms": tool_elapsed_ms,
                    "content_len": len(res.content or ""),
                    "content_preview": (res.content or "")[:4000],
                },
            )

        _assert_can_append_tool(ctx, tc.id)
        ctx.session.append(Message(role="tool", content=res.content, tool_call_id=tc.id))

    return True

def run_agent_once(
    ctx: AppContext,
    user_prompt: str | None,
    max_steps: int = 20,
    *,
    resume: bool = True,
) -> str:

    # 🔒 Clean any persisted invalid tool messages FIRST (fix old polluted sessions)
    _clean_invalid_tool_messages(ctx)

    # Phase 2: allow agent to override max_steps.
    if ctx.agent and ctx.agent.max_steps is not None:
        max_steps = ctx.agent.max_steps

    # Ensure system prompt at beginning (only once per session file)
    if not any(m.role == "system" for m in ctx.session.messages):
        ctx.session.append(Message(role="system", content=SYSTEM_PROMPT))

    # Crash recovery: best-effort, protocol-safe
    if resume:
        _resume_pending_tool_calls(ctx)
        # Resume may append tools; clean again defensively
        _clean_invalid_tool_messages(ctx)

    if user_prompt is not None:
        ctx.session.append(Message(role="user", content=user_prompt))

    tools = _tool_specs_to_openai(ctx.tools)

    step = 0
    final_text = ""
    policy = CompactionPolicy()

    provider_name = (getattr(ctx.provider, "provider_name", "") or "").lower()
    is_deepseek = ("deepseek" in provider_name) or ("deepseek" in model_name)

    while step < max_steps:

        # Phase 2: agent may override model.
        _orig_model = ctx.provider.model
        try:
            if ctx.agent and ctx.agent.model:
                ctx.provider.model = ctx.agent.model

            # ✅ Recompute per-step flags AFTER model override (fix mismatch)
            model_name = (getattr(ctx.provider, "model", "") or "").lower()
            is_reasoner = (model_name == "deepseek-reasoner")

            thinking_with_tools = ("deepseek-chat" in model_name)

            if is_reasoner:
                raise RuntimeError(
                    "deepseek-reasoner is not compatible with tool-calling loop in this runner."
                )

            force_reasoning = is_deepseek and thinking_with_tools
            include_reasoning = force_reasoning

            # Build prompt (uses per-step include/force)
            prompt_res = build_prompt_messages(
                cwd=ctx.cwd,
                session_messages=ctx.session.messages,
                provider=ctx.provider,
                policy=policy,
                include_reasoning_content=include_reasoning,
                force_reasoning_content=force_reasoning,
                ensure_skill=True,
                rules_text=ctx.rules_text,
                agent_prompt=(ctx.agent.system_prompt if ctx.agent else None),
            )

            if prompt_res.new_summary_message is not None:
                ctx.session.append(prompt_res.new_summary_message)
            prompt_res.messages = _clean_invalid_tool_dict_messages(prompt_res.messages)

            # 🔒 Validate outgoing messages BEFORE calling provider (catch locally)
            _validate_openai_messages(prompt_res.messages)

            if ctx.events:
                ctx.events.append(
                    "llm.request",
                    {
                        "step": step,
                        "model": ctx.provider.model,
                        "messages_count": len(prompt_res.messages),
                        "tools_count": len(tools),
                        "prompt_chars": _prompt_char_count(prompt_res.messages),
                    },
                )

            def _chat_once() -> "AssistantTurn":
                # Streaming: show tokens as they arrive.
                if ctx.stream:
                    def _on_token(tok: str) -> None:
                        try:
                            console.print(tok, end="")
                            console.file.flush()
                        except Exception:
                            pass

                    t = ctx.provider.chat(
                        prompt_res.messages,
                        tools=tools,
                        stream=True,
                        on_token=_on_token,
                    )
                    if t.text:
                        console.print()
                    return t

                return ctx.provider.chat(prompt_res.messages, tools=tools)

            # Robustness: retry transient provider failures a few times.
            last_err: Exception | None = None
            for attempt in range(3):
                try:
                    t0 = time.perf_counter()
                    turn = _chat_once()
                    llm_elapsed_ms = int((time.perf_counter() - t0) * 1000)
                    last_err = None
                    break
                except Exception as e:
                    last_err = e
                    if ctx.events:
                        ctx.events.append(
                            "llm.error",
                            {"step": step, "attempt": attempt + 1, "error": str(e)[:2000]},
                        )
                    time.sleep(0.5 * (2 ** attempt))

            if last_err is not None:
                # Persist error into the session for reproducibility.
                err_text = f"❌ LLM call failed after retries: {last_err}"
                ctx.session.append(Message(role="assistant", content=err_text))
                return err_text

        finally:
            ctx.provider.model = _orig_model
        if ctx.events:
            ctx.events.append(
                "llm.response",
                {
                    "step": step,
                    "elapsed_ms": locals().get("llm_elapsed_ms"),
                    "text": (turn.text or "")[:4000],
                    "tool_calls": [
                        {"id": tc.id, "name": tc.name, "arguments": tc.arguments}
                        for tc in (turn.tool_calls or [])
                    ],
                },
            )

        # Build assistant tool call echo
        assistant_tool_calls = None
        if turn.tool_calls:
            assistant_tool_calls = []
            for i, tc in enumerate(turn.tool_calls):
                if not tc.id:
                    tc.id = f"tc_{ctx.session.session_id}_{step}_{i}_{uuid.uuid4().hex[:8]}"
                assistant_tool_calls.append({
                    "id": tc.id,
                    "type": "function",
                    "function": {
                        "name": tc.name,
                        "arguments": json.dumps(tc.arguments or {}, ensure_ascii=False),
                    },
                })

        # Append assistant message (STRICT protocol)
        if assistant_tool_calls:
            assistant_msg = Message(
                role="assistant",
                content=None,
                tool_calls=assistant_tool_calls,
                reasoning_content=(turn.reasoning_content if include_reasoning else None),
            )
        else:
            assistant_msg = Message(
                role="assistant",
                content=turn.text or "",
                reasoning_content=(turn.reasoning_content if include_reasoning else None),
            )

        ctx.session.append(assistant_msg)

        # Record latest text (candidate final)
        if turn.text:
            final_text = turn.text

        # TRACE
        if ctx.trace:
            console.print(
                Align.center(
                    f"[bold red]🚨 This is the {ordinal(step + 1)} step 🚨[/bold red]"
                )
            )

            console.print(
                Panel.fit(
                    json.dumps(prompt_res.messages, ensure_ascii=False, indent=2)[:4000],
                    title="LLM INPUT (messages)",
                    border_style="cyan",
                )
            )

            llm_output = {
                "text": turn.text,
                "reasoning_content": turn.reasoning_content,
                "tool_calls": [
                    {"id": tc.id, "name": tc.name, "arguments": tc.arguments}
                    for tc in (turn.tool_calls or [])
                ],
            }
            console.print(
                Panel.fit(
                    json.dumps(llm_output, ensure_ascii=False, indent=2)[:4000],
                    title="LLM OUTPUT",
                    border_style="magenta",
                )
            )

        # If no tool calls: FINAL
        if not turn.tool_calls:
            if turn.text:
                return turn.text
            else:
                # 🔁 Model produced only reasoning or empty output, continue loop
                if ctx.events:
                    ctx.events.append(
                        "llm.empty_response",
                        {"step": step, "reason": "no text and no tool_calls"}
                    )
                step += 1
                continue


        step += 1

        # Execute tool calls sequentially
        for tc in turn.tool_calls:
            tool = ctx.tools.get_optional(tc.name)
            args = tc.arguments or {}
            preview = _args_preview(args)

            if tool is None:
                # Still respond with tool message to satisfy protocol
                if ctx.events:
                    ctx.events.append(
                        "tool.missing",
                        {"step": step, "tool": tc.name, "tool_call_id": tc.id},
                    )
                _assert_can_append_tool(ctx, tc.id)
                ctx.session.append(
                    Message(role="tool", content=f"Tool {tc.name} not found.", tool_call_id=tc.id)
                )
                continue

            if ctx.events:
                ctx.events.append(
                    "tool.call",
                    {
                        "step": step,
                        "tool": tool.spec.name,
                        "permission_key": tool.spec.permission_key,
                        "tool_call_id": tc.id,
                        "args": args,
                    },
                )

            allowed = ctx.permissions.decide(tool.spec.permission_key, tool.spec.name, preview)
            if not allowed:
                denied_msg = f"Tool {tool.spec.name} was denied by user permissions."
                if ctx.events:
                    ctx.events.append(
                        "tool.denied",
                        {"step": step, "tool": tool.spec.name, "tool_call_id": tc.id},
                    )
                _assert_can_append_tool(ctx, tc.id)
                ctx.session.append(Message(role="tool", content=denied_msg, tool_call_id=tc.id))
                continue

            tctx = ToolContext(cwd=str(ctx.cwd), session_id=ctx.session.session_id)
            t0 = time.perf_counter()
            try:
                res: ToolResult = tool.execute(tctx, args)
            except Exception as e:
                res = ToolResult(content=f"Tool {tool.spec.name} exception: {e}", is_error=True)
            tool_elapsed_ms = int((time.perf_counter() - t0) * 1000)

            if ctx.events:
                ctx.events.append(
                    "tool.result",
                    {
                        "step": step,
                        "tool": tool.spec.name,
                        "tool_call_id": tc.id,
                        "is_error": bool(res.is_error),
                        "elapsed_ms": tool_elapsed_ms,
                        "content_len": len(res.content or ""),
                        "content_preview": (res.content or "")[:4000],
                    },
                )

            # Truncate overly-long tool results to keep context manageable.
            if res.content and len(res.content) > policy.max_tool_result_chars:
                head = res.content[: policy.max_tool_result_chars // 2]
                tail = res.content[-policy.max_tool_result_chars // 2:]
                res = ToolResult(
                    content=head + "\n\n... (truncated) ...\n\n" + tail,
                    is_error=res.is_error,
                )

            if ctx.trace:
                console.print(
                    Panel.fit(
                        res.content[:1200] + ("..." if len(res.content) > 1200 else ""),
                        title=f"tool:{tool.spec.name} ({'error' if res.is_error else 'ok'})",
                        border_style="red" if res.is_error else "green",
                    )
                )

            _assert_can_append_tool(ctx, tc.id)
            ctx.session.append(Message(role="tool", content=res.content, tool_call_id=tc.id))

        # Continue to next LLM step after tools

    # If we exit by max_steps
    return final_text or "❌ Reached max steps without final answer"
