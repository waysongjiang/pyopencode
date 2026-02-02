# pyopencode 代码结构与执行流程（Phase 0 + Phase 1）

本文件面向“需要二次开发/扩展”的读者，解释核心模块职责、数据流、以及新增 Provider/Tools 的改动点。

---

## 目录结构总览（核心模块）

- `src/pyopencode/main.py`
  - CLI 入口（Typer）：`run` / `repl`
  - 解析参数：`--provider` `--config` `--cwd` `--session` `--yes` 等
  - 创建 `AppContext`，调用 `run_agent_once()`

- `src/pyopencode/app_context.py`
  - 组装运行所需组件：
    - `provider`（LLM 客户端）
    - `tools`（ToolRegistry，内置工具集合）
    - `permissions`（PermissionGate）
    - `session`（SessionStore）

- `src/pyopencode/runner.py`
  - 核心循环：**LLM ↔ Tools ↔ Session**
  - 负责：
    - 写入 system prompt / user prompt 到 session
    - 把 tools spec 转成 OpenAI tool schema
    - 请求 provider.chat 得到 assistant turn（text/tool_calls）
    - 把 assistant message（含 tool_calls）写回 session
    - 执行 tool_calls，把 tool 输出写回 session
    - 迭代直到没有 tool_calls 或达到 max_steps

- `src/pyopencode/session/`
  - `models.py`：Message / AssistantTurn / ToolCall 等数据结构
  - `store.py`：SessionStore（JSONL 落盘 & to_openai_messages）

- `src/pyopencode/tools/`
  - `registry.py`：ToolRegistry（注册/查询/list_specs）
  - `permissions.py`：PermissionGate（allow/ask/deny）
  - `builtin.py`：注册内置工具入口
  - `builtin_tools/`：各工具实现（listdir/glob/grep/read/write/edit/multiedit/patch/bash）

- `src/pyopencode/llm/`
  - `openai_compat.py`：OpenAI-compatible chat completions 客户端
  - `factory.py`：从 `pyopencode.yaml` 加载 provider 并 resolve

---

## 核心执行流程（run_agent_once）

以 `pyopencode run --prompt ...` 为例，流程如下：

### Step 1：初始化 Context
`main.py` 中创建 `AppContext`：
- `resolve_provider()` 读取 `pyopencode.yaml` 中对应 provider 配置（base_url/model/api_key）
- `register_builtin_tools()` 注册内置工具到 ToolRegistry
- `PermissionGate` 创建默认权限配置（read allow / edit ask / bash ask）
- `SessionStore.open()` 读取或创建 session（JSONL）

### Step 2：写入 System + User 到 Session
`runner.run_agent_once()`：
- 若 session 中还没有 system message，则写入 `SYSTEM_PROMPT`
- 把用户输入 `user_prompt` 追加到 session

### Step 3：构造 tools schema（OpenAI 格式）
`_tool_specs_to_openai()` 把每个 ToolSpec 转成：
```json
{
  "type": "function",
  "function": {
    "name": "...",
    "description": "...",
    "parameters": {...}
  }
}
```

### Step 4：调用 LLM（provider.chat）
- `ctx.session.to_openai_messages()` 生成 messages（role/content/tool_calls/tool_call_id）
- `provider.chat(messages, tools=tools)` 返回 `AssistantTurn`，包含：
  - `text`（content）
  - `tool_calls`（若模型发起工具调用）

### Step 5：把 assistant（含 tool_calls）写入 session
runner 会把 ToolCall 写成 OpenAI tool_calls 结构落盘，便于复现。

### Step 6：执行工具调用（按顺序）
对每个 tool_call：
- PermissionGate 决策（allow/ask/deny）
- 允许则调用 tool.execute(ctx, args) 得到 ToolResult
- tool 输出以 `role="tool"`、并带 `tool_call_id` 的 Message 写回 session

### Step 7：循环下一轮
- 如果没有 tool_calls：
  - 有文本 → 返回最终答案
  - 无文本 → 继续下一轮（用于一些“先思考但没产出”的模型输出）
- 达到 max_steps 返回最后一次文本或报错提示

---

## 数据结构（Session JSONL）

### Message（核心字段）
- `role`: system/user/assistant/tool
- `content`: 文本内容
- `tool_calls`: 仅 assistant 使用，记录发起的工具调用（列表）
- `tool_call_id`: 仅 tool 使用，指向对应 tool_calls 的 id
- `reasoning_content`: DeepSeek 等可能返回的推理字段（可选）

### 常见坑：孤儿 tool 消息（400 Bad Request）
如果你在构造 messages 时出现：
- tool message 存在，但前面没有对应 assistant 的 tool_calls  
则 OpenAI-compatible 服务会返回：  
`Messages with role 'tool' must be a response to a preceding message with 'tool_calls'`

根因通常是：
- 做了窗口裁剪/压缩，总结掉了 assistant(tool_calls) 但保留了 tool

建议的工程规则：
- 以“tool-call block”为单位裁剪：`assistant(tool_calls)` + 后续 `tool` 必须成组保留或成组丢弃。

---

## 扩展点（最常改的 2 类）

### 1) 新增工具（Tools）
改动点：
- 新建工具：`src/pyopencode/tools/builtin_tools/<new_tool>.py`
- 注册：`src/pyopencode/tools/builtin.py`

建议规范：
- 参数 schema 要尽量小、字段明确
- 输出要可复用：返回结构化文本（例如 JSON 或带标题的段落）
- 对危险工具使用 `permission_key="bash"` 或新增 permission key 并扩展 PermissionConfig

### 2) 新增模型/供应商（Provider）
如果目标服务是 OpenAI-compatible：
- 不用写新 provider，直接在 `pyopencode.yaml` 增加一个 providers 条目（base_url/model/api_key）

如果不是 OpenAI-compatible：
- 新增 `src/pyopencode/llm/<vendor>.py` 实现 chat()
- 在 factory 中注册/resolve
- 最重要：把响应统一转换成内部的 `AssistantTurn(text, tool_calls, reasoning_content)` 格式

---

## 如何自测（建议）
新增最小回归用例：
1) list+read
2) write+patch
3) bash 执行 `python -c "print(1)"`

并把 session 文件留存用于排查。
