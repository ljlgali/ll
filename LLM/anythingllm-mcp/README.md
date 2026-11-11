# AnythingLLM MCP Server

基于 AnythingLLM 的 MCP 服务器（HTTP / Streamable 传输，MCP 规范 2026-07-28）。

## 功能
三个工具，对应三类能力（不是同一个功能的三个名字）：

| 工具 | 能力类别 | 说明 |
|---|---|---|
| `list_workspaces` | 工作区管理 | 列出工作区 slug / 名称 / 文档数，用于确认真实 slug |
| `upload_document(file_path, workspace_slug="")` | 文档上传与向量化 | 上传本地文件到指定工作区，带 `addToWorkspaces` 触发嵌入 |
| `ask_workspace(question, workspace_slug="")` | 对话与检索问答 | 基于工作区文档做 RAG 问答，返回回答与参考来源 |

`workspace_slug` 留空时自动使用 `ANYTHINGLLM_WORKSPACE_SLUG` 或第一个工作区。
缺 `ANYTHINGLLM_API_KEY`、`ANYTHINGLLM_BASE_URL` 非法时，工具直接抛可读中文错误，不会把上游 401 透传给模型。

## 环境要求
- Python 3.10+
- 本机已启动 AnythingLLM（默认 http://localhost:3001）
- MCP Python SDK `mcp==2.0.0`（2.x 已移除 `mcp.server.fastmcp`，本项目用 `mcp.server.mcpserver.MCPServer`）

## 安装
```bash
cd /d E:\LLM\anythingllm-mcp
pip install -r requirements.txt
```

## 配置
复制 `.env.example` 为 `.env`，填入真实 API Key：
```ini
ANYTHINGLLM_BASE_URL=http://localhost:3001
ANYTHINGLLM_API_KEY=your-api-key-here
ANYTHINGLLM_WORKSPACE_SLUG=
MCP_HOST=0.0.0.0
MCP_PORT=8000
```
> `.env` 已加入 .gitignore，不会入库；`WORKSPACE_SLUG` 留空时自动使用第一个工作区。

## 启动
前台启动（调试用，Ctrl+C 停止）：
```bash
python server.py
```

后台启动：
```bash
start /B python server.py > server.log 2>&1
```
或双击 `start.bat`。

服务地址：`http://127.0.0.1:8000/mcp`

## 停止
- 前台启动：按 `Ctrl+C`
- 后台启动：双击 `stop.bat`，或：
```bash
netstat -ano | findstr :8000
taskkill /F /PID <PID>
```

## 项目级 MCP 配置
项目根目录 `.mcp.json`：
```json
{
  "mcpServers": {
    "anythingllm": {
      "type": "http",
      "url": "http://127.0.0.1:8000/mcp"
    }
  }
}
```

## 验证
用 MCP Inspector 或客户端连接 `http://127.0.0.1:8000/mcp`：
1. `list_workspaces()` -> 确认工作区 slug
2. `upload_document(file_path="E:/tmp/test.txt")` -> 上传并向量化
3. `ask_workspace(question="文档里讲了什么？")` -> 得到带来源的回答

## 传输实现
`server.py` 用 `MCPServer.streamable_http_app()` 生成 ASGI app，`uvicorn` 挂载到 `MCP_ENDPOINT_PATH`（默认 `/mcp`）。
`python server.py` 等价于在该 host/port 上起一个 Streamable HTTP 端点。
