# LAgent

基于 `core / tui` 分层架构的本地 Agent，前端为 Textual 终端界面。除常规文件操作与联网工具外，支持 **Skill 动态加载** 与 **MCP（Model Context Protocol）Client**，可在不修改代码的前提下扩展能力。

## 功能特性

- 多轮对话 + 流式输出，工具调用结果实时展示（含耗时）
- 16 个内置工具：时间、文件系统、联网搜索/抓取、命令行执行
- **Skill 机制**：扫描 `.agents/skills/`，只把 `name` + `description` 注入 System Prompt，正文按需 `loadSkill` 加载
- **MCP Client**：读取 `.mcp.json`，通过 MCP SDK 连接外部 Server，将其工具动态注册为本地 Function Calling 工具
- Esc 中断、会话重置、会话统计（`session_id` / 轮次 / 工具次数）
- core 层零界面依赖，可复用于 Web / Desktop / Mobile 前端

## 目录结构

```
LAgent/
├── main.py                入口：把项目根加入 sys.path 后启动 TUI
├── config.ini             LLM 配置（与 main.py 同目录）
├── .mcp.json              MCP Server 配置
├── .agents/skills/        Skill 目录（每个 Skill 一个子目录）
│   └── <skill-name>/
│       ├── SKILL.md       YAML Frontmatter + 正文
│       └── ...            附件文件（由 loadSkill 的 filename 指定读取）
├── core/                  业务核心层（无任何界面代码）
│   ├── config.py          读取 config.ini，创建 OpenAI 兼容客户端
│   ├── tools.py           build_system_prompt() + 全部工具 JSON Schema
│   ├── functions.py       工具实现 + dispatch 统一分发
│   ├── skills.py          Skill 发现、Frontmatter 解析、按需加载
│   ├── mcp_client.py      MCP 配置读取、连接、工具注册与调用转发
│   └── agent.py           Agent：历史管理、流式请求、工具循环、统计
└── tui/                   终端界面层（不含业务逻辑）
    └── app.py             对话区 / 输入框 / 右侧栏 / Slash 命令
```

## 环境准备

```powershell
D:\东软软件\课堂python\.venv\Scripts\python.exe -m pip install openai textual mcp
```

`config.ini`：

```ini
[llm]
base_url = https://api.deepseek.com
api_key = sk-xxxxxxxxxxxxxxxx
model = deepseek-chat

[search]
baidu_qianfan_api_key = xxxxxxxx
```

## 运行

```powershell
cd /d E:\LLM\LLM\Agent\LAgent
D:\东软软件\课堂python\.venv\Scripts\python.exe main.py
```

`main.py` 按自身所在目录定位 `config.ini` 与项目根，`cwd` 只影响「工作目录」显示和相对路径工具。

## 内置工具

| 工具名 | 功能 |
|---|---|
| getDate | 获取本机当前日期时间 |
| isLeapYear | 判断闰年（参数 `year`） |
| getCwd | 获取当前工作目录 |
| listFiles | 列出目录内容（参数 `path`） |
| getFileType | 扩展名 / MIME / 是否纯文本 |
| readFile | 读取纯文本文件 |
| createFile | 新建文件（已存在则报错） |
| editFile | 编辑文件（`overwrite` / `append`） |
| createDir | 创建目录（支持多级） |
| deleteDir | 删除非空目录 |
| deleteFile | 删除文件 |
| renamePath | 重命名文件或目录 |
| searchWeb | 联网搜索（参数 `query`） |
| fetchWeb | 抓取网页正文为 Markdown（参数 `url`） |
| RunCli | 执行本地命令行程序（`command` + `args`） |
| loadSkill | 加载 Skill 正文或附件（`name` 必填，`filename` 可选） |

工具结果超过 4000 字符会截断并标注原始长度。

## Skill 机制

**目录**：`core/skills.py` 中 `AGENTS_ROOT_CANDIDATES` 依次扫描
`E:/Office/.agents/skills`（作业运行目录）与项目根 `.agents/skills`。

**SKILL.md 格式**：

```markdown
---
name: meeting-notes
description: 将会议记录整理成结构规范的会议纪要。触发词：整理会议纪要、会议总结。
---
# 会议纪要整理
（正文：只有调用 loadSkill 时才进入上下文）
```

**加载流程**：

1. 启动 / `/new` 时 `discover_skills()` 只读 Frontmatter 的 `name`、`description`
2. `build_system_prompt(skills, mcp)` 把技能清单写进 System Prompt
3. 模型判断相关时调用 `loadSkill(name, filename?)`，正文才进入上下文
4. 附件读取做路径穿越防护：`resolve().relative_to(skill_path)`，越界一律拒绝

## MCP Client

**配置** `项目根/.mcp.json`：

```json
{
  "mcpServers": {
    "Bazi-MCP": {
      "type": "streamable_http",
      "url": "https://mcp.api-inference.modelscope.net/xxxx/mcp"
    }
  }
}
```

**工作流程**：

1. 启动时 `MCPManager.start()` 读配置（查找顺序：`cwd` → 项目根）
2. 后台线程运行独立 asyncio 事件循环，用 `streamable_http_client` 连接并常驻
3. `initialize()` → `list_tools()` 发现工具
4. 转成 OpenAI Function Calling Schema，与本地工具合并为同一份 `tools` 列表
5. LLM 调用时经 `dispatch()` 转发到对应 Server，结果归一化（文本块 / 结构化数据 / 错误标记）后回传

**名称冲突**：与本地工具或其它 Server 重名时自动加前缀，例如 `Srv-A__readFile`。

**容错**：连接失败会拆解 `ExceptionGroup` 输出真实原因（如 `ConnectError: All connection attempts failed`），本地工具不受影响；单个调用超时 30 秒。

## TUI 命令与快捷键

| 命令 | 作用 |
|---|---|
| `/new`、`/reset`、`/clear` | 重置会话（重新发现 Skill，MCP 连接保持不变） |
| `/skills` | 列出已发现的 Skill |
| `/mcp` | 查看 MCP Server 连接状态与已注册工具 |
| `/help`、`/?` | 帮助 |

`Ctrl+C` 退出，`Esc` 中断当前生成。

## 作为库调用

`core.Agent.chat_stream()` 返回事件生成器：

```python
from core import Agent

agent = Agent()
for ev in agent.chat_stream("帮我查一下今天的黄历"):
    if ev["type"] == "token":      # 流式文本
        print(ev["content"], end="")
    elif ev["type"] == "tool":     # 工具调用：name / args / result / elapsed_ms
        print(f"\n[工具 {ev['name']}] {ev['elapsed_ms']:.0f}ms")
    elif ev["type"] == "done":     # 结束：reply
        break
    elif ev["type"] == "error":    # 异常：message
        print("错误", ev["message"])
```

新增前端只需消费该事件流，core 层无需改动。

## 已知限制

- MCP 仅支持 Streamable HTTP（`type: streamable_http`），stdio 类型暂未接入
- `.mcp.json` 查找只覆盖「当前目录」与「项目根」两处
