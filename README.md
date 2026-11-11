# LLM 课程 MCP 开发项目

课程 MCP 开发 MVP 最小原型项目，共 4 个部分：3 个 MCP / 网页开发任务，外加 1 个自研本地 Agent（LAgent）。

## 目录结构

```
LLM/
├── Agent/
│   ├── LAgent/                 # 自研本地 Agent（Skill + MCP Client + TUI）
│   ├── Practice01/             # 课程练习 1
│   └── practice02/             # 课程练习 2（对话程序 + 架构图）
├── pet-hospital-mcp/           # 任务 1：宠物医院 MCP 服务（第一次任务）
├── anythingllm-mcp/            # 任务 2：AnythingLLM MCP 服务（第二次任务）
└── anythingLLMServer/          # 任务 3：AnythingLLM 文件上传网页（第三次任务）
```

| 目录 | 内容 | 技术要点 |
|---|---|---|
| `pet-hospital-mcp/` | 宠物医院 MCP Server（工具 `list_pets`，对接 `GET /api/v1/pets`） | MCP 2.0 `MCPServer` + Streamable HTTP，含 35 项 pytest 单测 |
| `anythingllm-mcp/` | AnythingLLM MCP Server（工作区管理 / 文档上传向量化 / 工作区问答 3 个工具） | MCP 2.0 `MCPServer` + Streamable HTTP，httpx 调 AnythingLLM REST API |
| `anythingLLMServer/` | AnythingLLM 文档上传网页（`POST /v1/document/upload`） | 单页 HTML + 前端直连 REST API |
| `Agent/LAgent/` | 本地 Agent：18 个内置工具 + Skill 动态加载 + MCP Client + Textual TUI | core/tui 分层，路径边界、工具循环上限、落盘日志 |

## 任务 1：pet-hospital-mcp（第一次开发任务）

开发宠物医院 MCP Server MVP 版本。

- 对接 PetHospitalServer 后端 REST API
- MCP 工具：`list_pets`，对应接口 `GET /api/v1/pets`，实现宠物列表查询（分页、过滤、排序）
- 通信方式：Streamable HTTP，兼容新旧 MCP 协议（2026-07-28 前后版本）
- 自带 pytest 单测，运行方式见该目录 README

## 任务 2：anythingllm-mcp（第二次开发任务）

开发对接本机 AnythingLLM 的 MCP Server MVP 版本，把 AnythingLLM 的三类能力封装成 MCP 工具。

- 调用本机 AnythingLLM 的 REST API（`/v1/...`），使用自定义 API Key
- 工具与能力对应：
  - `list_workspaces` —— **工作区管理**：列出工作区 slug / 名称 / 文档数
  - `upload_document` —— **文档上传与向量化**：本地文件上传到指定工作区并触发嵌入（`addToWorkspaces`）
  - `ask_workspace` —— **对话与检索问答**：基于工作区文档做 RAG 问答，返回回答与参考来源
- 通信方式：Streamable HTTP，兼容新旧 MCP 协议
- 缺 `ANYTHINGLLM_API_KEY` / URL 非法时给出可读中文错误，不透传上游 401

> 说明：早期版本只实现了「读取第一个工作区的文件信息」单一功能，现已扩展为上述三类能力，
> 与本 README 及 `anythingllm-mcp/README.md` 保持一致。

## 任务 3：anythingLLMServer（第三次开发任务）

开发简单网页，给 AnythingLLM 第一个工作区上传文档并自动向量化嵌入。

- 使用 REST API：`POST /v1/document/upload`
- 功能：文档上传 + 向量化处理
- 极简设计，不做冗余开发，节约 token

## 附加：Agent/LAgent（非课程任务，自研扩展）

一个基于 `core / tui` 分层的本地 Agent，终端界面为 Textual。

- 18 个内置工具（时间、文件系统、联网搜索/抓取、命令行、Skill 管理、历史检索）
- **Skill 机制**：只把 `name` + `description` 注入 System Prompt，正文按 `loadSkill` 按需加载
- **MCP Client**：读取 `.mcp.json`，支持 Streamable HTTP 与 stdio 两种传输，把远端工具动态注册为本地工具
- 安全与保护：文件工具路径边界、危险操作二次校验、单轮工具次数与超时上限、`.agents/logs/agent.log` 落盘日志
- 详见 `Agent/LAgent/README.md`

## 快速开始（分步）

```powershell
# 任务 1：宠物医院 MCP（需先启动 Go 后端 pethospital.exe，默认 127.0.0.1:8080）
cd LLM\pet-hospital-mcp
python -m venv .venv
.venv\Scripts\python.exe -m pip install -e ".[test]"
.venv\Scripts\python.exe -m pet_hospital_mcp      # MCP 端点 http://127.0.0.1:8000/mcp

# 任务 2：AnythingLLM MCP（需先启动本机 AnythingLLM，默认 localhost:3001）
cd ..\anythingllm-mcp
pip install -r requirements.txt
copy .env.example .env                            # 填入 ANYTHINGLLM_API_KEY
python server.py                                  # MCP 端点 http://127.0.0.1:8000/mcp

# 任务 3：上传网页
# 直接双击 anythingLLMServer\upload.html，填 API Key 后选文件上传

# 附加：LAgent
cd ..\Agent\LAgent
pip install openai textual "mcp==2.0.0" requests trafilatura
# 在 config.ini 填 [llm] 的 base_url / api_key / model
python main.py
```

每个子项目的详细配置、验证步骤与已知限制见各自 README。

## 开发环境

- Python 3.10+
- MCP Python SDK `mcp==2.0.0`（本仓库统一使用 `mcp.server.mcpserver.MCPServer`）
- PetHospitalServer（宠物医院后端服务，提供 REST 接口）
- AnythingLLM 本地服务（默认 `http://localhost:3001`）

## 项目说明

全部项目均为 MVP 最小原型版本，不做冗余、过度设计，减少 token 消耗。
使用 Git 进行版本管理，分任务提交代码。
