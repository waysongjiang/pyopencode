# pyopencode 代码详解（逐文件/逐模块）

> 本文档面向“读代码 + 二次开发”的场景：解释每个核心文件做什么、关键函数如何串起来、数据结构怎么流动、以及你改动/扩展应落在哪里。
>
> 说明：关键路径包括：
> - `src/pyopencode/main.py`
> - `src/pyopencode/app_context.py`
> - `src/pyopencode/runner.py`
> - `src/pyopencode/llm/openai_compat.py`
> - `src/pyopencode/llm/factory.py`
> - `src/pyopencode/session/models.py`
> - `src/pyopencode/session/store.py`
> - `src/pyopencode/tools/*`

---

## 1. 从命令行到核心循环：入口调用链

### 1.1 `src/pyopencode/__main__.py`
- 作用：允许你用 `python -m pyopencode ...` 启动 CLI。
- 一般会调用 `main.py` 里的 app（Typer）或 main 函数。

### 1.2 `src/pyopencode/main.py`（CLI 入口）
- 作用：解析 CLI 参数，创建 `AppContext`，调用 `runner.run_agent_once()`。
- 你会在这里看到常见参数：
  - `--prompt/-p`：用户输入
  - `--provider`：从 `pyopencode.yaml` 选择 provider
  - `--model/--base-url/--api-key`：覆盖 YAML 默认值
  - `--cwd`：工作目录（传给 tools）
  - `--yes`、`--no-bash`、`--allow-edit`：权限相关

> 扩展建议：如果你要新增命令（如 `stats`、`events`、`replay` 等），通常就在 `main.py` 增加一个 Typer command，然后调用对应模块函数。

---

## 2. AppContext：把 Provider/Tools/Session/Permissions 组装起来

### 2.1 `src/pyopencode/app_context.py`
核心类：`AppContext`（dataclass）
- `cwd: Path`：项目工作目录
- `provider: OpenAICompatProvider`：LLM 客户端（OpenAI-compatible）
- `tools: ToolRegistry`：工具注册表（tool name -> tool 实例）
- `permissions: PermissionGate`：权限门控（allow/ask/deny）
- `session: SessionStore`：会话存储（JSONL）
- `auto_approve: bool`：是否自动批准危险工具

关键工厂方法：`AppContext.from_env(...)`
- 调用 `llm.factory.resolve_provider(...)` 创建 provider
- 调用 `tools.builtin.register_builtin_tools(...)` 注册内置工具
- 构造 `PermissionConfig.default()` 并应用 CLI 覆盖：
  - `deny_bash` -> `bash=deny`
  - `allow_edit` -> `edit=allow`
  - `auto_approve` -> `edit=allow` 且 `bash=allow`
- 通过 `SessionStore.open(session_id)` 打开/新建 session（JSONL 文件）

> 扩展落点：新增 provider/新增工具/新增 session 能力（断点续跑/回放）通常都不改 `AppContext` 逻辑，只要在 `resolve_provider` 或 `register_builtin_tools` 等处扩展即可。

---

## 3. Session：消息数据结构与 JSONL 落盘

### 3.1 `src/pyopencode/session/models.py`
这里定义了最核心的数据结构（建议先读懂）：
- `Message`：你落盘的最小单位（每条一行 JSON）
  - `role`: `"system"|"user"|"assistant"|"tool"`
  - `content`: 文本
  - `tool_calls`: 仅 assistant 使用（OpenAI tool_calls 结构）
  - `tool_call_id`: 仅 tool 使用，指向它在上一条 assistant.tool_calls 中对应的 `id`
  - `reasoning_content`: 某些 provider 会返回（如 DeepSeek），可选
- `ToolCall`：内部工具调用结构（id/name/arguments）
- `AssistantTurn`：provider.chat 的返回对象
  - `text`: assistant content
  - `tool_calls`: List[ToolCall]
  - `reasoning_content`: 可选

关键方法：`Message.to_openai(...)`
- 把内部 `Message` 转换为 OpenAI-compatible 的 `messages` 列表元素，供 provider.chat 发送。

### 3.2 `src/pyopencode/session/store.py`
核心类：`SessionStore`
- `SessionStore.open(session_id=None)`：
  - session_id 为空则生成 12 位随机 id
  - session 文件路径：`platformdirs.user_data_dir("pyopencode")/sessions/<sid>.jsonl`
  - 若文件存在：逐行 `json.loads` 恢复 `Message` 列表
- `append(msg)`：
  - 追加到内存 `messages`
  - 追加写入 JSONL（每条一行）
- `to_openai_messages(...)`：
  - 逐条调用 `Message.to_openai`，返回 provider 所需的 messages 数组

> 工程注意：目前是“直接 append + 写文件”，如果你要做更强稳定性（崩溃恢复），可改为：flush/fsync + 读取时跳过坏行。

---

## 4. Provider：OpenAI-compatible Chat Completions 客户端

### 4.1 `src/pyopencode/llm/openai_compat.py`
核心类：`OpenAICompatProvider`
- 输入：`messages`（OpenAI message array）+ 可选 `tools`
- 输出：`AssistantTurn(text, tool_calls, reasoning_content)`

关键逻辑：`chat(...)`
1) 拼 URL：`base_url.rstrip("/") + "/chat/completions"`
2) 组 payload：
   - `model`, `messages`, `temperature`
   - 若传入 tools：加上 `tools` 和 `tool_choice="auto"`
3) 用 `urllib.request` 发 POST（Header 用 Bearer token）
4) 解析返回：
   - `obj["choices"][0]["message"]["content"]`
   - `message["tool_calls"]`（如果存在）
5) 逐条解析 tool_calls：
   - `function.name`
   - `function.arguments`（json string -> dict）
   - 生成内部 `ToolCall(id, name, arguments)`

> 扩展建议：
> - 如果你要支持 streaming：需要改为 SSE 解析（vLLM/OpenAI/兼容网关会返回 `data: {...}`）。
> - 如果你要支持“工具调用 fallback”：当 tool_calls 为空时，尝试从 content 解析 `{"tool": "...", "args": {...}}`。

### 4.2 `src/pyopencode/llm/factory.py`
职责：从 `pyopencode.yaml` 加载 provider 列表，并按 `--provider` 解析出最终配置。
关键点：
- `load_provider_registry("pyopencode.yaml")`
  - YAML 结构：
    ```yaml
    providers:
      deepseek:
        PYOPENCODE_BASE_URL: "..."
        PYOPENCODE_MODEL: "..."
        PYOPENCODE_API_KEY: "${ENV_VAR}"
    ```
  - 支持 `${ENV_VAR}` 占位符注入（`_expand_env_placeholders`）
- `resolve_provider(provider, model, base_url, api_key)`
  - CLI 参数优先覆盖 YAML 默认值
  - 最终返回 `OpenAICompatProvider(model, base_url, api_key)`

> 你要新增一个“名字叫 qwen / doubao / openai”的 provider：只需在 `pyopencode.yaml` 加一个 providers 条目，不需要写新代码（前提：它是 OpenAI-compatible）。

---

## 5. Tools：协议、注册表、权限门控、内置工具实现

### 5.1 `src/pyopencode/tools/base.py`
定义了工具协议与基础数据结构：
- `ToolSpec`：工具元信息（会被转成 OpenAI tool schema）
  - `name` / `description`
  - `parameters`：JSONSchema（**很关键**，影响模型能否正确调用）
  - `permission_key`：`"read" | "edit" | "bash"`（用于权限决策）
- `Tool`（Protocol）：每个工具必须有 `spec` 和 `execute(ctx, args)`
- `ToolContext`：目前只有 `cwd`（工具执行的工作目录）
- `ToolResult`：`content` + `is_error`

### 5.2 `src/pyopencode/tools/registry.py`
`ToolRegistry` 的职责：
- 注册：`register(tool)`
- 查询：`get(name)`
- 列出 schema：`list_specs()`（供 runner 转 OpenAI tool schema）

### 5.3 `src/pyopencode/tools/permissions.py`
`PermissionGate`：工具调用前的最终闸门
- `PermissionConfig.default()` 默认：
  - `read=allow`
  - `edit=ask`
  - `bash=ask`
- `decide(permission_key, tool_name, args_preview)`：
  - allow -> True
  - deny -> False
  - ask -> 若 `auto_approve=True` 则 True，否则在终端询问 `Approve? [y/N]`

> 设计要点：把“工具危险等级”抽象成 permission_key，新增危险工具时，只需指定 permission_key 即可复用门控逻辑。

### 5.4 `src/pyopencode/tools/builtin.py`
`register_builtin_tools(registry)`：集中注册内置工具。
- 新增工具时，通常就是：
  1) 在 `builtin_tools/` 新建文件实现 Tool
  2) 在这里 import 并 register

### 5.5 `src/pyopencode/tools/builtin_tools/*`（内置工具）
常见工具文件（以你压缩包为准）：
- `file_read.py`：读文件
- `glob_tool.py`：通配符匹配
- `grep_tool.py`：内容搜索
- `file_write.py`：写文件
- `file_edit.py` / `file_multiedit.py`：按行范围修改
- `patch_tool.py`：应用 patch/diff
- `bash_tool.py`：执行命令

每个工具都遵循同一模式：
- `spec = ToolSpec(...)`
- `execute(ctx, args) -> ToolResult`

> 工具实现建议：
> - 输出要“可被模型继续消费”：带标题、分段、必要时输出 JSON。
> - 写入类工具尽量确定性（按行号/patch），避免“模糊编辑”。

---

## 6. Runner：LLM ↔ Tools ↔ Session 的核心循环（最重要）

### 6.1 `src/pyopencode/runner.py` 概览
核心函数：`run_agent_once(ctx, user_prompt, max_steps=20) -> str`

关键结构：
1) **SYSTEM_PROMPT 注入**：
   - session 中没有 system message 才追加一次 `SYSTEM_PROMPT`
2) 追加 user message：`ctx.session.append(Message(role="user", content=user_prompt))`
3) tools schema：`_tool_specs_to_openai(ctx.tools)`
4) while 循环：每轮调用一次 LLM + 执行若干工具

### 6.2 LLM 调用与 assistant 写回
- `include_reasoning = (ctx.provider.provider_name == "deepseek")`
- `turn = ctx.provider.chat(ctx.session.to_openai_messages(...), tools=tools)`
- 将 `turn.tool_calls` 转成 OpenAI tool_calls 结构并写入 session：
  - `Message(role="assistant", content=turn.text, tool_calls=[...], reasoning_content=...)`

### 6.3 终止条件（你代码里有一个关键分支）
```python
if not turn.tool_calls:
    if turn.text:
        return turn.text
    else:
        continue
```
含义：
- 没有 tool_calls 且有文本 -> 直接当最终答案返回
- 没有 tool_calls 且无文本 -> 继续下一轮（防止模型“只思考没输出”导致提前结束）

### 6.4 执行工具调用（按顺序）
对每个 `tc in turn.tool_calls`：
1) `tool = ctx.tools.get(tc.name)`
2) `allowed = ctx.permissions.decide(tool.spec.permission_key, tool.spec.name, preview)`
3) 执行：`tool.execute(ToolContext(cwd=str(ctx.cwd)), args)`
4) 写 tool message：`Message(role="tool", content=res.content, tool_call_id=tc.id)`

并且用 Rich `Panel` 打印工具输出摘要，方便你在终端观察链路。

---

## 7. 常见错误与定位（强烈建议读）

### 7.1 400：tool message 必须跟随 tool_calls
错误：
```
Messages with role 'tool' must be a response to a preceding message with 'tool_calls'
```
含义：你发给 provider 的 `messages` 中出现了 `role="tool"`，但在它之前没有对应的 `assistant` 消息带 `tool_calls`。
常见根因：
- 做了“消息裁剪/压缩”，把 assistant(tool_calls) 丢了但 tool 结果还在
- 断点续跑/回放写入 tool message 时没有保留对应 assistant(tool_calls)

解决原则：**以 tool-call block 为单位处理消息**：
- `assistant(tool_calls)` + 后续对应 `tool` 必须成组保留/成组删除
- 发送前可以做校验：发现“孤儿 tool”就丢弃或降级成普通文本

### 7.2 工具调用失败（工具找不到）
- 检查 `ToolRegistry` 是否注册了该工具名
- 检查工具名与 tool spec 是否一致（区分大小写/下划线）

### 7.3 参数 JSON 解析失败
- `openai_compat.py` 里对 `function.arguments` 做 `json.loads`，如果模型输出非 JSON 会变成 `{}`。
- 解决：在系统 prompt 强约束“工具 arguments 必须是 JSON”。

---

## 8. 你要新增模型（qwen/openai/豆包）应该改哪里？

**如果它提供 OpenAI-compatible endpoint：只改 `pyopencode.yaml`**  
- 在 `providers:` 下新增一个 name（比如 `qwen`），填三项：
  - `PYOPENCODE_BASE_URL`
  - `PYOPENCODE_MODEL`
  - `PYOPENCODE_API_KEY`（建议 `${ENV}`）
然后运行时 `--provider qwen` 即可。

**如果它不是 OpenAI-compatible：新增 provider 文件并在 factory 中分流**  
- 新建：`src/pyopencode/llm/<vendor>.py` 实现 `chat()` 返回 `AssistantTurn`
- 修改：`resolve_provider()` 支持 `type` 字段（例如 `type: doubao_native`）或按 provider 名称判断

---

## 9. 建议的“下一步工程化增强”（不改变架构前提）
1) Session 写入崩溃安全：append 加 flush/fsync + open 时跳坏行
2) streaming：SSE parser + 边输出边落盘
3) tool-call block window：避免“孤儿 tool”400
4) replay/resume：基于 session 的断点续跑/重放工具执行（利于 debug 与可复现）

---

## 10. 快速导航：我改功能时一般怎么查
- 想改 LLM 请求：`llm/openai_compat.py`
- 想改 provider 配置解析：`llm/factory.py`
- 想加工具：`tools/builtin_tools/*` + `tools/builtin.py`
- 想改权限策略：`tools/permissions.py`
- 想改核心循环/终止条件：`runner.py`
- 想改落盘格式：`session/models.py` + `session/store.py`
