from __future__ import annotations

from pathlib import Path
import json
import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.align import Align

from datetime import datetime

from .app_context import AppContext
from .runner import run_agent_once
from .config.loader import load_behavior_config
from .commands.loader import discover_commands, load_command, render_command_prompt
from .llm.factory import load_provider_registry
from .session.store import SessionStore
from .events.store import EventStore
from .tools.base import ToolContext, ToolResult

from .mcp.client import MCPClient
from .session.models import Message


def _iter_assistant_tool_calls(store: SessionStore):
    """Yield (assistant_index, tool_calls_dict_list, following_tool_messages)"""
    msgs = store.messages
    for i, m in enumerate(msgs):
        if m.role != "assistant" or not m.tool_calls:
            continue
        # collect contiguous tool messages immediately after this assistant
        following: list[Message] = []
        for j in range(i + 1, len(msgs)):
            if msgs[j].role != "tool":
                break
            following.append(msgs[j])
        yield i, (m.tool_calls or []), following


app = typer.Typer(add_completion=False, help="pyopencode: local modular coding agent (Phase 0-4).")
console = Console()


def _default_cwd() -> Path:
    return Path.cwd()


def _resolve_cwd(cwd: Path | None) -> Path:
    cwd = cwd or _default_cwd()
    cwd = Path(str(cwd)).expanduser()
    if not cwd.is_absolute():
        cwd = (Path.cwd() / cwd).resolve()
    else:
        cwd = cwd.resolve()
    if cwd.exists() and not cwd.is_dir():
        raise typer.BadParameter(f"--cwd must be a directory, got file: {cwd}")
    if not cwd.exists():
        cwd.mkdir(parents=True, exist_ok=True)
    return cwd


def _load_selected_provider(config: Path, provider: str):
    reg = load_provider_registry(config)
    cfg = reg.get(provider)
    return cfg, reg


@app.command()
def run(
    prompt: str = typer.Option(..., "--prompt", "-p", help="User prompt to run once."),
    provider: str = typer.Option(..., "--provider", help="Provider name registered in YAML (e.g. deepseek/kimi/openai/qwen)."),
    config: Path = typer.Option(Path("pyopencode.yaml"), "--config", help="YAML config path (default: ./pyopencode.yaml)."),
    cwd: Path = typer.Option(None, "--cwd", help="Working directory (project root). Defaults to current directory."),
    session: str = typer.Option(None, "--session", help="Session id to append to (default creates new)."),
    yes: bool = typer.Option(False, "--yes", help="Auto-approve tools that require confirmation (edit/bash)."),
    no_bash: bool = typer.Option(False, "--no-bash", help="Deny bash tool."),
    allow_edit: bool = typer.Option(False, "--allow-edit", help="Auto-allow edit tools (write/edit/patch)."),
    max_steps: int = typer.Option(25, "--max-steps", help="Max tool/LLM iterations."),
    agent: str = typer.Option("general", "--agent", help="Agent profile (general/plan/explore/build/run or custom)."),
    behavior_config: Path = typer.Option(None, "--behavior-config", help="Optional behavior JSON (pyopencode.json) path."),
    trace: bool = typer.Option(True, "--trace", help="Print LLM input/output and tool traces."),
    stream: bool = typer.Option(False, "--stream", help="Stream tokens while generating."),
    resume: bool = typer.Option(True, "--resume/--no-resume", help="Resume pending tool calls before running."),
):
    cwd = _resolve_cwd(cwd)

    cfg, reg = _load_selected_provider(config, provider)
    cfg_path = Path(config).expanduser().resolve() if config else None
    ctx = AppContext.from_env(
        cwd=cwd,
        session_id=session,
        provider=cfg.name,
        model=cfg.model,
        base_url=cfg.base_url,
        api_key=cfg.api_key,
        auto_approve=yes,
        deny_bash=no_bash,
        allow_edit=allow_edit or yes,
        agent_name=agent,
        behavior_config=behavior_config,
        trace=trace,
        stream=stream,
        config_path=cfg_path,
    )

    table = Table.grid(padding=(0, 2))

    table.add_row("📁 [bold green]cwd[/bold green]", f"[bright_cyan]{ctx.cwd}[/bright_cyan]")
    table.add_row("🆔 [bold green]session[/bold green]", f"[bright_cyan]{ctx.session.session_id}[/bright_cyan]")
    table.add_row("🔌 [bold green]provider[/bold green]", f"[bright_cyan]{cfg.name}[/bright_cyan]")
    table.add_row("🧠 [bold green]model[/bold green]", f"[bright_cyan]{cfg.model}[/bright_cyan]")
    table.add_row("🌐 [bold green]base_url[/bold green]", f"[bright_cyan]{cfg.base_url}[/bright_cyan]")
    table.add_row("🤖 [bold green]agent[/bold green]", f"[bright_cyan]{ctx.agent.name if ctx.agent else 'general'}[/bright_cyan]")
    table.add_row("⚙️ [bold green]behavior_config[/bold green]", f"[bright_cyan]{ctx.behavior_config_path or '(none)'}[/bright_cyan]")
    table.add_row("📦 [bold green]known providers[/bold green]", f"[bright_cyan]{', '.join(reg.names())}[/bright_cyan]")

    console.print(
	    Align.center(
	        Panel(
	            table,
	            title="[bold magenta]pyopencode[/bold magenta]",
	            border_style="bright_blue",
	        )
	    )
	)
    try:
        console.print(f"\n[bold]You:[/bold] {prompt}\n")
        answer = run_agent_once(ctx, user_prompt=prompt, max_steps=max_steps, resume=resume)
        console.print("\n[bold]Assistant:[/bold]\n")
        console.print(answer)
    finally:
        ctx.close()


@app.command()
def repl(
    provider: str = typer.Option(..., "--provider", help="Provider name registered in YAML (e.g. deepseek/kimi/openai/qwen)."),
    config: Path = typer.Option(Path("pyopencode.yaml"), "--config", help="YAML config path (default: ./pyopencode.yaml)."),
    cwd: Path = typer.Option(None, "--cwd", help="Working directory (project root). Defaults to current directory."),
    session: str = typer.Option(None, "--session", help="Session id to append to (default creates new)."),
    yes: bool = typer.Option(False, "--yes", help="Auto-approve tools that require confirmation (edit/bash)."),
    no_bash: bool = typer.Option(False, "--no-bash", help="Deny bash tool."),
    allow_edit: bool = typer.Option(False, "--allow-edit", help="Auto-allow edit tools (write/edit/patch)."),
    max_steps: int = typer.Option(100, "--max-steps", help="Max tool/LLM iterations per message."),
    agent: str = typer.Option("general", "--agent", help="Agent profile (general/plan/explore/build/run or custom)."),
    behavior_config: Path = typer.Option(None, "--behavior-config", help="Optional behavior JSON (pyopencode.json) path."),
    trace: bool = typer.Option(True, "--trace", help="Print LLM input/output and tool traces."),
    stream: bool = typer.Option(False, "--stream", help="Stream tokens while generating."),
    resume: bool = typer.Option(True, "--resume/--no-resume", help="Resume pending tool calls before each turn."),
):
    cwd = _resolve_cwd(cwd)

    cfg, reg = _load_selected_provider(config, provider)
    cfg_path = Path(config).expanduser().resolve() if config else None
    ctx = AppContext.from_env(
        cwd=cwd,
        session_id=session,
        provider=cfg.name,
        model=cfg.model,
        base_url=cfg.base_url,
        api_key=cfg.api_key,
        auto_approve=yes,
        deny_bash=no_bash,
        allow_edit=allow_edit or yes,
        agent_name=agent,
        behavior_config=behavior_config,
        trace=trace,
        stream=stream,
        config_path=cfg_path,
    )

    table = Table.grid(padding=(0, 2))

    table.add_row("📁 [bold green]cwd[/bold green]", f"[bright_cyan]{ctx.cwd}[/bright_cyan]")
    table.add_row("🆔 [bold green]session[/bold green]", f"[bright_cyan]{ctx.session.session_id}[/bright_cyan]")
    table.add_row("🔌 [bold green]provider[/bold green]", f"[bright_cyan]{cfg.name}[/bright_cyan]")
    table.add_row("🧠 [bold green]model[/bold green]", f"[bright_cyan]{cfg.model}[/bright_cyan]")
    table.add_row("🌐 [bold green]base_url[/bold green]", f"[bright_cyan]{cfg.base_url}[/bright_cyan]")
    table.add_row("🤖 [bold green]agent[/bold green]", f"[bright_cyan]{ctx.agent.name if ctx.agent else 'general'}[/bright_cyan]")
    table.add_row("⚙️ [bold green]behavior_config[/bold green]", f"[bright_cyan]{ctx.behavior_config_path or '(none)'}[/bright_cyan]")
    table.add_row("📦 [bold green]known providers[/bold green]", f"[bright_cyan]{', '.join(reg.names())}[/bright_cyan]")

    console.print(
	    Align.center(
	        Panel(
	            table,
	            title="[bold magenta]pyopencode[/bold magenta]",
	            border_style="bright_blue",
	        )
	    )
	)

    try:
        while True:
            try:
                user = typer.prompt("You")
            except (EOFError, KeyboardInterrupt):
                break
            if user.strip().lower() in {"exit", "quit"}:
                break
            # Special command: /continue -> resume pending tool calls and continue without adding a new user message.
            if user.strip() == "/continue":
                answer = run_agent_once(ctx, user_prompt=None, max_steps=max_steps, resume=resume)
            else:
                answer = run_agent_once(ctx, user_prompt=user, max_steps=max_steps, resume=resume)
            console.print("\n[bold]Assistant:[/bold]\n")
            console.print(answer)
            console.print()
    finally:
        ctx.close()

@app.command()
def commands(
    cwd: Path = typer.Option(None, "--cwd", help="Working directory (project root). Defaults to current directory."),
    behavior_config: Path = typer.Option(None, "--behavior-config", help="Optional behavior JSON (pyopencode.json) path."),
):
    """List available commands discovered from commands/ directories and behavior config."""
    cwd = _resolve_cwd(cwd)
    behavior = load_behavior_config(cwd=cwd, explicit_path=behavior_config)
    cmds = discover_commands(cwd=cwd, inline=behavior.commands)
    if not cmds:
        console.print("No commands found.")
        raise typer.Exit(code=0)
    for name in sorted(cmds.keys()):
        spec = cmds[name]
        desc = spec.description or ""
        agent = spec.agent or ""
        extra = f" (agent={agent})" if agent else ""
        console.print(f"- [bold]{name}[/bold]{extra} {desc}")

@app.command()
def cmd(
    name: str = typer.Argument(..., help="Command name (from commands/ or behavior config)."),
    provider: str = typer.Option(..., "--provider", help="Provider name registered in YAML (e.g. deepseek/kimi/openai/qwen)."),
    config: Path = typer.Option(Path("pyopencode.yaml"), "--config", help="YAML config path (default: ./pyopencode.yaml)."),
    cwd: Path = typer.Option(None, "--cwd", help="Working directory (project root). Defaults to current directory."),
    session: str = typer.Option(None, "--session", help="Session id to append to (default creates new)."),
    yes: bool = typer.Option(False, "--yes", help="Auto-approve tools that require confirmation (edit/bash)."),
    no_bash: bool = typer.Option(False, "--no-bash", help="Deny bash tool."),
    allow_edit: bool = typer.Option(False, "--allow-edit", help="Auto-allow edit tools (write/edit/patch)."),
    max_steps: int = typer.Option(50, "--max-steps", help="Max tool/LLM iterations."),
    agent: str = typer.Option(None, "--agent", help="Override agent profile for this command."),
    behavior_config: Path = typer.Option(None, "--behavior-config", help="Optional behavior JSON (pyopencode.json) path."),
    arg: list[str] = typer.Option(None, "--arg", "-A", help="Template args as key=value; used in {{key}} placeholders."),
    trace: bool = typer.Option(False, "--trace", help="Print LLM input/output and tool traces."),
    stream: bool = typer.Option(False, "--stream", help="Stream tokens while generating."),
    resume: bool = typer.Option(True, "--resume/--no-resume", help="Resume pending tool calls before running."),
):
    """Run a reusable command template (Phase 3)."""
    cwd = _resolve_cwd(cwd)
    cfg, reg = _load_selected_provider(config, provider)

    behavior = load_behavior_config(cwd=cwd, explicit_path=behavior_config)
    spec = load_command(cwd=cwd, name=name, inline=behavior.commands)

    # Parse args
    args: dict[str, str] = {}
    for it in (arg or []):
        if "=" in it:
            k, v = it.split("=", 1)
            args[k.strip()] = v
    prompt = render_command_prompt(spec, args)

    # command may specify agent/model/max_steps
    chosen_agent = agent or spec.agent or behavior.default_agent
    chosen_model = spec.model or cfg.model
    chosen_max_steps = spec.max_steps if spec.max_steps is not None else max_steps
    cfg_path = Path(config).expanduser().resolve() if config else None
    ctx = AppContext.from_env(
        cwd=cwd,
        session_id=session,
        provider=cfg.name,
        model=chosen_model,
        base_url=cfg.base_url,
        api_key=cfg.api_key,
        auto_approve=yes,
        deny_bash=no_bash,
        allow_edit=allow_edit or yes,
        agent_name=chosen_agent,
        behavior_config=behavior_config,
        trace=trace,
        stream=stream,
        config_path=cfg_path,
    )

    # Show header
    console.print(
        Panel.fit(
            f"[bold]command:[/bold] {spec.name}\n"
            f"[bold]cwd:[/bold] {ctx.cwd}\n"
            f"[bold]session:[/bold] {ctx.session.session_id}\n"
            f"[bold]provider:[/bold] {cfg.name}\n"
            f"[bold]model:[/bold] {ctx.agent.model if ctx.agent and ctx.agent.model else cfg.model}\n"
            f"[bold]agent:[/bold] {ctx.agent.name if ctx.agent else chosen_agent}\n"
            f"[bold]behavior_config:[/bold] {ctx.behavior_config_path or '(none)'}\n",
            title="pyopencode CMD",
        )
    )

    # Apply command overrides for model/max_steps by temporarily patching agent
    if ctx.agent:
        if spec.model:
            ctx.agent.model = spec.model
        if spec.max_steps is not None:
            ctx.agent.max_steps = spec.max_steps

    try:
        answer = run_agent_once(ctx, user_prompt=prompt, max_steps=chosen_max_steps, resume=resume)
        console.print("\n[bold]Assistant:[/bold]\n")
        console.print(answer)
    finally:
        ctx.close()


@app.command()
def mcp(
    cwd: Path = typer.Option(None, "--cwd", help="Working directory (project root). Defaults to current directory."),
    behavior_config: Path = typer.Option(None, "--behavior-config", help="Optional behavior JSON (pyopencode.json) path."),
):
    """List configured MCP servers and discovered MCP tools."""
    cwd = _resolve_cwd(cwd)
    behavior = load_behavior_config(cwd=cwd, explicit_path=behavior_config)
    if not behavior.mcp_servers:
        console.print("No MCP servers configured. Add mcp_servers to pyopencode.json.")
        raise typer.Exit(code=0)
    for name, sc in behavior.mcp_servers.items():
        console.print(f"[bold]{name}[/bold] -> {sc.command} (prefix={sc.prefix or 'mcp.'+name})")
    # start each server and list tools (no LLM provider needed)
    clients: list[MCPClient] = []
    try:
        all_tools: list[tuple[str, str]] = []
        for name, sc in behavior.mcp_servers.items():
            client = MCPClient(sc.command, cwd=sc.cwd, env=sc.env)
            clients.append(client)
            prefix = sc.prefix or f"mcp.{name}"
            for t in client.list_tools():
                all_tools.append((f"{prefix}.{t.name}", t.description or ""))
        if not all_tools:
            console.print("No MCP tools discovered.")
        else:
            console.print("\nDiscovered MCP tools:")
            for n, d in sorted(all_tools, key=lambda x: x[0]):
                console.print(f"- [bold]{n}[/bold]: {d}")
    finally:
        for c in clients:
            try:
                c.close()
            except Exception:
                pass


@app.command()
def continue_run(
    provider: str = typer.Option(..., "--provider", help="Provider name registered in YAML (e.g. deepseek/kimi/openai/qwen)."),
    config: Path = typer.Option(Path("pyopencode.yaml"), "--config", help="YAML config path (default: ./pyopencode.yaml)."),
    cwd: Path = typer.Option(None, "--cwd", help="Working directory (project root). Defaults to current directory."),
    session: str = typer.Option(..., "--session", help="Session id to continue (required)."),
    yes: bool = typer.Option(False, "--yes", help="Auto-approve tools that require confirmation (edit/bash)."),
    no_bash: bool = typer.Option(False, "--no-bash", help="Deny bash tool."),
    allow_edit: bool = typer.Option(False, "--allow-edit", help="Auto-allow edit tools (write/edit/patch)."),
    max_steps: int = typer.Option(50, "--max-steps", help="Max tool/LLM iterations."),
    agent: str = typer.Option("general", "--agent", help="Agent profile."),
    behavior_config: Path = typer.Option(None, "--behavior-config", help="Optional behavior JSON (pyopencode.json) path."),
    trace: bool = typer.Option(False, "--trace", help="Print LLM input/output and tool traces."),
    stream: bool = typer.Option(False, "--stream", help="Stream tokens while generating."),
):
    """Continue a session without adding a new user message.

    Useful for crash recovery: if the previous run persisted tool_calls but didn't finish tool execution,
    this will resume and then continue the agent loop.
    """
    cwd = _resolve_cwd(cwd)
    cfg, reg = _load_selected_provider(config, provider)
    cfg_path = Path(config).expanduser().resolve() if config else None
    ctx = AppContext.from_env(
        cwd=cwd,
        session_id=session,
        provider=cfg.name,
        model=cfg.model,
        base_url=cfg.base_url,
        api_key=cfg.api_key,
        auto_approve=yes,
        deny_bash=no_bash,
        allow_edit=allow_edit or yes,
        agent_name=agent,
        behavior_config=behavior_config,
        trace=trace,
        stream=stream,
        config_path=cfg_path
    )
    console.print(
        Panel.fit(
            f"[bold]cwd:[/bold] {ctx.cwd}\n"
            f"[bold]session:[/bold] {ctx.session.session_id}\n"
            f"[bold]provider:[/bold] {cfg.name}\n"
            f"[bold]model:[/bold] {cfg.model}\n"
            f"[bold]agent:[/bold] {ctx.agent.name if ctx.agent else 'general'}\n",
            title="pyopencode CONTINUE",
        )
    )
    try:
        answer = run_agent_once(ctx, user_prompt=None, max_steps=max_steps, resume=True)
        console.print("\n[bold]Assistant:[/bold]\n")
        console.print(answer)
    finally:
        ctx.close()


@app.command()
def replay(
    session: str = typer.Option(..., "--session", help="Session id to replay."),
    tail: int = typer.Option(50, "--tail", help="Show last N messages."),
    show_system: bool = typer.Option(False, "--show-system", help="Include system messages."),
):
    """Replay recent conversation messages from a saved session."""
    store = SessionStore.open(session_id=session)
    msgs = store.messages
    if not show_system:
        msgs = [m for m in msgs if m.role != "system"]
    msgs = msgs[-tail:] if tail and tail > 0 else msgs

    console.print(Panel.fit(f"session: {store.session_id}\nfile: {store.path}", title="Replay"))
    for m in msgs:
        title = f"{m.role}"
        if m.role == "tool":
            title = f"tool ({m.tool_call_id})"
        console.print(Panel(m.content or "", title=title))


@app.command()
def events(
    session: str = typer.Option(..., "--session", help="Session id to inspect events."),
    tail: int = typer.Option(200, "--tail", help="Show last N events."),
):
    """Show recent structured events (LLM calls, tool calls) recorded for a session."""
    es = EventStore.open(session)
    evs = list(es.iter_events())
    evs = evs[-tail:] if tail and tail > 0 else evs
    console.print(Panel.fit(f"session: {session}\nfile: {es.path}\nevents: {len(evs)}", title="Events"))
    for e in evs:
        ts = datetime.fromtimestamp(e.ts).strftime("%Y-%m-%d %H:%M:%S")
        console.print(Panel.fit(json.dumps(e.data, ensure_ascii=False, indent=2)[:4000], title=f"{ts}  {e.type}"))


@app.command()
def stats(
    session: str = typer.Option(..., "--session", help="Session id to summarize."),
):
    """Show a compact observability summary for a session (latency, errors, tool usage)."""
    es = EventStore.open(session)
    evs = list(es.iter_events())

    llm_req = [e for e in evs if e.type == "llm.request"]
    llm_res = [e for e in evs if e.type == "llm.response"]
    llm_err = [e for e in evs if e.type == "llm.error"]

    tool_call = [e for e in evs if e.type == "tool.call"]
    tool_res = [e for e in evs if e.type == "tool.result"]
    tool_den = [e for e in evs if e.type == "tool.denied"]

    def _avg_ms(items):
        vals = []
        for e in items:
            ms = (e.data or {}).get("elapsed_ms")
            if isinstance(ms, (int, float)) and ms >= 0:
                vals.append(float(ms))
        return (sum(vals) / len(vals)) if vals else None

    llm_avg = _avg_ms(llm_res)
    tool_avg = _avg_ms(tool_res)

    freq = {}
    for e in tool_call:
        t = (e.data or {}).get("tool")
        if not t:
            continue
        freq[t] = freq.get(t, 0) + 1
    top_tools = sorted(freq.items(), key=lambda x: x[1], reverse=True)[:12]

    lines = []
    lines.append(f"session: {session}")
    lines.append(f"events_file: {es.path}")
    lines.append(f"llm_requests: {len(llm_req)}  llm_responses: {len(llm_res)}  llm_errors: {len(llm_err)}")
    if llm_avg is not None:
        lines.append(f"llm_avg_latency_ms: {llm_avg:.1f}")
    lines.append(f"tool_calls: {len(tool_call)}  tool_results: {len(tool_res)}  tool_denied: {len(tool_den)}")
    if tool_avg is not None:
        lines.append(f"tool_avg_latency_ms: {tool_avg:.1f}")
    if top_tools:
        lines.append("top_tools:")
        for name, c in top_tools:
            lines.append(f"  - {name}: {c}")

    console.print(Panel.fit("\n".join(lines), title="Stats"))


@app.command()
def replay_exec(
    session: str = typer.Option(..., "--session", help="Session id to replay tool execution from."),
    provider: str = typer.Option(..., "--provider", help="Provider name (only used to build context/tools)."),
    config: Path = typer.Option(Path("pyopencode.yaml"), "--config", help="YAML config path."),
    cwd: Path = typer.Option(None, "--cwd", help="Working directory (project root)."),
    yes: bool = typer.Option(False, "--yes", help="Auto-approve tools that require confirmation (edit/bash)."),
    no_bash: bool = typer.Option(False, "--no-bash", help="Deny bash tool."),
    allow_edit: bool = typer.Option(False, "--allow-edit", help="Auto-allow edit tools."),
    behavior_config: Path = typer.Option(None, "--behavior-config", help="Optional behavior JSON (pyopencode.json) path."),
    dry_run: bool = typer.Option(False, "--dry-run", help="Do not execute tools; only show what would run."),
    start: int = typer.Option(0, "--start", help="Start from assistant tool-call index (0-based)."),
    limit: int = typer.Option(999999, "--limit", help="Max assistant tool-call groups to process."),
):
    """Replay tool execution for a session (no LLM calls).

    This is useful to:
      - reproduce side effects (file edits, bash) from a recorded run
      - validate determinism of tool outputs

    It re-executes each assistant tool_call block in order and prints the results.
    """
    cwd = _resolve_cwd(cwd)
    cfg, _ = _load_selected_provider(config, provider)

    # Build a full context so tool registry, permissions, behavior rules are loaded.
    # Provider is not actually called during replay_exec.
    cfg_path = Path(config).expanduser().resolve() if config else None
    ctx = AppContext.from_env(
        cwd=cwd,
        session_id=session,
        provider=cfg.name,
        model=cfg.model,
        base_url=cfg.base_url,
        api_key=cfg.api_key,
        auto_approve=yes,
        deny_bash=no_bash,
        allow_edit=allow_edit or yes,
        agent_name=None,
        behavior_config=behavior_config,
        trace=False,
        stream=False,
        config_path=cfg_path,
    )

    store = ctx.session
    groups = list(_iter_assistant_tool_calls(store))
    groups = groups[start : start + limit]

    console.print(
        Panel.fit(
            f"session: {store.session_id}\nfile: {store.path}\nblocks: {len(groups)}\ndry_run: {dry_run}",
            title="Replay Exec",
        )
    )

    for gi, (assistant_index, tool_calls, following) in enumerate(groups, start=start):
        console.print(Panel.fit(f"assistant_index: {assistant_index}\nblock: {gi}", title="Tool Calls"))
        answered = {m.tool_call_id: (m.content or "") for m in following if m.tool_call_id}
        for tc in tool_calls:
            fn = (tc.get("function") or {})
            name = fn.get("name")
            tool_call_id = tc.get("id") or ""
            arg_str = fn.get("arguments") or "{}"
            try:
                args = json.loads(arg_str) if isinstance(arg_str, str) else (arg_str or {})
            except Exception:
                args = {}

            console.print(
                Panel.fit(
                    json.dumps({"tool": name, "tool_call_id": tool_call_id, "args": args}, ensure_ascii=False, indent=2)[:4000],
                    title=f"call: {name}",
                    border_style="cyan",
                )
            )

            if dry_run:
                continue
            if not name:
                console.print("[red]Missing tool name[/red]")
                continue

            tool = ctx.tools.get_optional(name)
            if tool is None:
                console.print(f"[red]Unknown tool:[/red] {name}")
                continue
            preview = json.dumps(args, ensure_ascii=False, indent=2)[:2000]
            allowed = ctx.permissions.decide(tool.spec.permission_key, tool.spec.name, preview)
            if not allowed:
                console.print(f"[yellow]Denied:[/yellow] {name}")
                continue

            tctx = ToolContext(cwd=str(ctx.cwd), session_id=store.session_id)
            try:
                res: ToolResult = tool.execute(tctx, args)
            except Exception as e:
                res = ToolResult(content=f"Tool {tool.spec.name} exception: {e}", is_error=True)

            old = answered.get(tool_call_id)
            mismatch = (old is not None) and (old.strip() != (res.content or "").strip())
            title = f"result: {name} ({'error' if res.is_error else 'ok'})"
            if mismatch:
                title += " [DIFF]"
            console.print(
                Panel.fit(
                    (res.content or "")[:4000],
                    title=title,
                    border_style="red" if res.is_error else ("yellow" if mismatch else "green"),
                )
            )
if __name__ == "__main__":
    app()
