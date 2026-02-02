# pyopencode (Phase 0-4)
一个本地运行、模块化的 Coding Agent，灵感来自 anomalyco/opencode。  
目标：用 **LLM ↔ Tools ↔ Session** 的标准循环，在本地项目中完成“读代码 → 改代码 → 运行命令 → 迭代修复”。

---

## 特性一览
- **本地 CLI**：支持 `run`（单次运行）与 `repl`（交互式）
- **OpenAI-compatible Provider**：可连接 OpenAI/DeepSeek/Kimi 等“兼容 OpenAI Chat Completions”的 API（通过统一客户端）
- **工具调用（Tools）**：文件读取/检索、文件写入/编辑/补丁、Bash 执行
- **权限门控（Permission Gate）**：默认 `read=allow, edit=ask, bash=ask`，支持 `--yes` 一键自动批准
- **会话持久化（Session）**：每次对话与工具输出以 JSONL 形式落盘，可复现与追踪

---

## 安装（推荐可编辑安装）
```bash
cd pyopencode
python -m venv .venv
# Windows: .venv\Scripts\activate
source .venv/bin/activate

pip install -U pip
pip install -e .
```

---

## Provider 配置（OpenAI-compatible）
项目通过 `pyopencode.yaml` 注册 provider。你也可以用环境变量占位符 `${ENV_VAR}` 来避免把 Key 写进仓库。

### 方式 A：通用 OpenAI-compatible（适用于多数兼容网关/本地 vLLM）
设置环境变量：
```bash
export PYOPENCODE_API_KEY="YOUR_KEY"
export PYOPENCODE_BASE_URL="https://api.openai.com/v1"   # 或任意兼容 endpoint
export PYOPENCODE_MODEL="gpt-4.1-mini"
```

> 注意：当前代码的 ProviderRegistry 主要从 `pyopencode.yaml` 读配置；通用环境变量方式更适合你在 YAML 里把 key 写成 `${PYOPENCODE_API_KEY}` 这种占位符。

### 方式 B：pyopencode.yaml（推荐，清晰可复用）
示例（`pyopencode.yaml`）：
```yaml
providers:
  deepseek:
    PYOPENCODE_BASE_URL: "https://api.deepseek.com/v1"
    PYOPENCODE_MODEL: "deepseek-chat"
    PYOPENCODE_API_KEY: "${DEEPSEEK_API_KEY}"

  kimi:
    PYOPENCODE_BASE_URL: "https://api.moonshot.ai/v1"
    PYOPENCODE_MODEL: "moonshot-v1-8k"
    PYOPENCODE_API_KEY: "${MOONSHOT_API_KEY}"

  openai:
    PYOPENCODE_BASE_URL: "https://api.openai.com/v1"
    PYOPENCODE_MODEL: "gpt-4o-mini"
    PYOPENCODE_API_KEY: "${OPENAI_API_KEY}"
```

---

## 快速开始

### 单次运行（run）
```bash
pyopencode run --prompt "Read src/app.py and explain what it does" --provider deepseek --cwd .
```

### 交互模式（repl）
```bash
pyopencode repl --provider deepseek --cwd .
```

### 自动批准（允许 edit/bash，无需每次询问）
```bash
pyopencode run --prompt "Create hello.py printing hello; run it" --provider deepseek --yes --cwd .
```

---

## 工具列表（Phase 0 + Phase 1）

### Phase 0（只读工具）
- `listdir`：列目录
- `glob`：通配符查找文件
- `grep`：内容搜索
- `read`：读文件

### Phase 1（写入/执行工具）
- `write`：写入文件（覆盖/创建）
- `edit`：按行范围修改（确定性编辑）
- `multiedit`：多段行范围修改
- `patch`：应用 diff/patch
- `bash`：执行 shell 命令（受权限门控）
- `webfetch`：抓取网页并转纯文本（若已集成）
- `todowrite/todoread`：会话级 TODO（若已集成）
- `skill`：读取 `SKILL.md` 注入规则（若已集成）
- `question`：结构化向用户提问（若已集成）

---

## 权限策略（Permission Gate）
默认：
- read：allow
- edit：ask
- bash：ask

参数：
- `--yes`：自动批准 edit/bash（无人值守运行）
- `--no-bash`：禁止 bash
- `--allow-edit`：允许所有 edit 类工具

---

## Session（会话落盘）
会话文件保存为 JSONL：每条消息一行，包含 role/content/tool_calls/tool_call_id 等字段。  
保存目录使用 `platformdirs.user_data_dir("pyopencode")/sessions`（不同系统路径不同）。

用途：
- 复盘 LLM 工具调用链
- Debug 复杂任务时定位“模型到底看到了什么”
- 支持后续扩展：断点续跑/重放执行/统计分析

---

## 开发者：如何扩展

### 新增工具（Tool）
1. 在 `src/pyopencode/tools/builtin_tools/` 下实现一个 Tool（继承 base.Tool）
2. 在 `src/pyopencode/tools/builtin.py` 的 `register_builtin_tools()` 中注册
3. Tool 需要提供：
   - `spec`（name/description/parameters/permission_key）
   - `execute(ctx, args)` 返回 `ToolResult(content, is_error)`

### 新增 Provider
当前实现为 OpenAI-compatible 客户端：
- `src/pyopencode/llm/openai_compat.py`：请求 `/chat/completions` 并解析 message/tool_calls
- `src/pyopencode/llm/factory.py`：读取 `pyopencode.yaml` 并创建 provider

如果你的新模型“不是 OpenAI-compatible”，建议新增一个 provider 类并在 factory 中注册/分流。

---

## 已知问题/常见错误
- `Messages with role 'tool' must be a response to a preceding message with 'tool_calls'`  
  说明 messages 序列中出现了“孤儿 tool 消息”：tool 结果前面缺少对应的 assistant(tool_calls)。  
  常见原因：做窗口裁剪/压缩时把 tool_calls 那条 assistant 丢了但保留了 tool。需要确保 tool-call block 不被拆散。
