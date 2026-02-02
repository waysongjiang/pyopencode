# pyopencode (Phase 0-4)

A local, modular coding agent scaffold inspired by anomalyco/opencode.

Included phases:
- Phase 1: builtin tools + context compaction
- Phase 2: behavior config + rules + agents
- Phase 3: commands + MCP bridge
- Phase 4: lightweight local code navigation (`lsp` tool) + structured event log/replay

## Install (editable)
```bash
cd pyopencode
python -m venv .venv
# windows: .venv\Scripts\activate
source .venv/bin/activate
pip install -U pip
pip install -e .
```

## Configure provider (OpenAI-compatible)

You can keep using the generic env vars (works for OpenAI-compatible endpoints), **or** use a provider preset
for DeepSeek / Kimi(Moonshot) / OpenAI.

### Option A: generic (any OpenAI-compatible endpoint)

```bash
export PYOPENCODE_API_KEY="YOUR_KEY"
export PYOPENCODE_BASE_URL="https://api.openai.com/v1"   # or any OpenAI-compatible endpoint
export PYOPENCODE_MODEL="gpt-4.1-mini"                   # change as you like
```

### Option B: presets (recommended)

#### OpenAI
```bash
export PYOPENCODE_PROVIDER="openai"
export OPENAI_API_KEY="YOUR_KEY"
# optional overrides:
# export PYOPENCODE_BASE_URL="https://api.openai.com"  # will auto-normalize to .../v1
# export PYOPENCODE_MODEL="gpt-4.1-mini"
```

#### DeepSeek
```bash
export PYOPENCODE_PROVIDER="deepseek"
export DEEPSEEK_API_KEY="YOUR_KEY"
# optional overrides:
# export PYOPENCODE_BASE_URL="https://api.deepseek.com"     # (or https://api.deepseek.com/v1)
# export PYOPENCODE_MODEL="deepseek-chat"                   # or deepseek-reasoner
```

#### Kimi (Moonshot)
```bash
export PYOPENCODE_PROVIDER="kimi"
export MOONSHOT_API_KEY="YOUR_KEY"
# optional overrides:
# export PYOPENCODE_BASE_URL="https://api.moonshot.ai"      # will auto-normalize to .../v1
# export MOONSHOT_API_BASE="https://api.moonshot.cn/v1"     # if you want China endpoint
# export PYOPENCODE_MODEL="moonshot-v1-8k"                  # or moonshot-v1-32k / moonshot-v1-128k / kimi-k2-*
```

## Run (single prompt)
```bash
pyopencode run "Read src/app.py and explain what it does" --cwd .
```

## Run with auto-approve edit/bash tools
```bash
pyopencode run "Create hello.py printing hello; run it" --yes --cwd .
```

## Notes
- Phase 0 tools: `read`, `list`, `glob`, `grep`
- Phase 1 tools: `write`, `edit`, `multiedit`, `patch`, `bash`
- Permissions default: `read=allow`, `edit=ask`, `bash=ask` (override with `--yes` or flags)

## Stability (resume / replay-exec / streaming)

This build includes three stability features:

- **Resume pending tool calls**: if a run crashes after persisting an assistant message containing `tool_calls` but before appending all tool results, the next run will automatically execute the missing tool calls and append corresponding `tool` messages. Toggle with `--resume/--no-resume`.
- **Streaming**: stream tokens while generating. Enable with `--stream`.
- **Replay execution (no LLM)**: re-run recorded tool calls from a session for reproducibility and determinism checks.

### Examples

```bash
# stream tokens
pyopencode run --provider deepseek --prompt "..." --stream

# continue a crashed session (no new user message)
pyopencode continue-run --provider deepseek --session <session_id> --stream

# replay tool execution only (no LLM calls)
pyopencode replay-exec --provider deepseek --session <session_id>

# dry-run replay
pyopencode replay-exec --provider deepseek --session <session_id> --dry-run
```
