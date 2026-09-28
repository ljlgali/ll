# AnythingLLM MCP Server

基于 AnythingLLM 的 MCP 服务器（HTTP / Streamable 传输，MCP 规范 2026-07-28）。

## 功能
- 唯一工具 `ask_workspace`：基于 AnythingLLM 指定工作区的文档进行 AI 问答（RAG）。

## 环境要求
- Python 3.10+
- 本机已启动 AnythingLLM（默认 http://localhost:3001）

## 安装
```bash
cd /d E:\LLM\anythingllm-mcp
pip install -r requirements.txt
```

## 配置
复制 `.env` 并确认内容：
```ini
ANYTHINGLLM_BASE_URL=http://localhost:3001
ANYTHINGLLM_API_KEY=W4938X4-63RMMTG-JXY5K7R-GFJMR26
ANYTHINGLLM_WORKSPACE_SLUG=
MCP_HOST=0.0.0.0
MCP_PORT=8000
```
> `WORKSPACE_SLUG` 留空时自动使用第一个工作区。

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
用 MCP Inspector 或客户端连接 `http://127.0.0.1:8000/mcp`，调用 `ask_workspace(question="...")`。
