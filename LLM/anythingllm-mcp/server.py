"""AnythingLLM MCP Server —— 把本机 AnythingLLM 的三类能力封装为 MCP 工具。

工具（按能力归类，不看命名）：
  1. 工作区管理       list_workspaces
  2. 文档上传/向量化   upload_document
  3. 对话与检索问答     ask_workspace

传输：Streamable HTTP（MCP 2026-07-28，`MCPServer.streamable_http_app`）。
SDK：与 pet-hospital-mcp 统一为 mcp==2.0.0（2.x 已移除 `mcp.server.fastmcp`）。
配置：全部来自环境变量 / .env；缺配置时抛可读错误，不把上游 401 透传给模型。
"""

import os
from pathlib import Path

import httpx
import uvicorn
from dotenv import load_dotenv
from mcp.server.mcpserver import MCPServer

load_dotenv()

BASE_URL = os.getenv("ANYTHINGLLM_BASE_URL", "http://localhost:3001").rstrip("/")
API_KEY = os.getenv("ANYTHINGLLM_API_KEY", "")
WORKSPACE_SLUG = os.getenv("ANYTHINGLLM_WORKSPACE_SLUG", "").strip()
REQUEST_TIMEOUT = float(os.getenv("ANYTHINGLLM_TIMEOUT", "120"))
MCP_HOST = os.getenv("MCP_HOST", "0.0.0.0")
MCP_PORT = int(os.getenv("MCP_PORT", "8000"))
MCP_PATH = os.getenv("MCP_ENDPOINT_PATH", "/mcp")

mcp = MCPServer(
    name="anythingllm-mcp",
    title="AnythingLLM MCP",
    description=(
        "AnythingLLM 的 MCP 适配层：工作区管理、文档上传与向量化、"
        "基于工作区文档的检索问答（RAG）。"
    ),
    version="1.0.0",
)

_workspace_slug: str | None = WORKSPACE_SLUG or None


# ---------- 配置校验与公共请求 ----------
def _check_config() -> None:
    """缺配置时抛可读错误（模型与用户都能看懂，而不是一串 401 堆栈）。"""
    if not API_KEY:
        raise RuntimeError(
            "未配置 ANYTHINGLLM_API_KEY：请在 anythingllm-mcp/.env 中填写 "
            "ANYTHINGLLM_API_KEY=你的 Key，或在进程环境变量里设置后重启服务。"
        )
    if not BASE_URL.lower().startswith(("http://", "https://")):
        raise RuntimeError(f"ANYTHINGLLM_BASE_URL 不合法：{BASE_URL}（需以 http:// 或 https:// 开头）")


def _headers() -> dict:
    return {"Authorization": f"Bearer {API_KEY}"}


async def _get_slug() -> str:
    """返回工作区 slug；未配置时自动取第一个工作区。"""
    global _workspace_slug
    _check_config()
    if _workspace_slug:
        return _workspace_slug
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.get(f"{BASE_URL}/v1/workspaces", headers=_headers())
    if resp.status_code != 200:
        raise _api_error("列出工作区", resp)
    workspaces = resp.json().get("workspaces", [])
    if not workspaces:
        raise RuntimeError("AnythingLLM 中没有任何工作区，请先在 AnythingLLM 里创建一个")
    _workspace_slug = workspaces[0]["slug"]
    return _workspace_slug


def _api_error(action: str, resp: httpx.Response) -> RuntimeError:
    """把上游失败翻译成带状态码与响应片段的可读错误。"""
    body = (resp.text or "")[:200]
    return RuntimeError(f"{action}失败：HTTP {resp.status_code}，响应片段：{body}")


# ---------- 能力 1：工作区管理 ----------
@mcp.tool(
    name="list_workspaces",
    description=(
        "列出 AnythingLLM 中的所有工作区（slug / 名称 / 文档数）。"
        "在不确定要往哪个工作区上传或提问时，先调用它确认真实 slug。"
    ),
    structured_output=False,
)
async def list_workspaces() -> str:
    _check_config()
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.get(f"{BASE_URL}/v1/workspaces", headers=_headers())
    if resp.status_code != 200:
        raise _api_error("列出工作区", resp)
    workspaces = resp.json().get("workspaces", [])
    if not workspaces:
        return "当前没有任何工作区"
    lines = [f"共 {len(workspaces)} 个工作区："]
    for w in workspaces:
        docs = w.get("documents") or []
        lines.append(f"- slug={w.get('slug')} | name={w.get('name')} | 文档 {len(docs)} 个")
    return "\n".join(lines)


# ---------- 能力 2：文档上传 + 向量化 ----------
@mcp.tool(
    name="upload_document",
    description=(
        "把本地文件上传到 AnythingLLM 指定工作区并触发向量化嵌入（addToWorkspaces）。"
        "file_path 为本地绝对路径；workspace_slug 留空则用配置值或第一个工作区。"
    ),
    structured_output=False,
)
async def upload_document(file_path: str, workspace_slug: str = "") -> str:
    _check_config()
    p = Path(file_path).expanduser()
    if not p.is_file():
        raise RuntimeError(f"文件不存在：{file_path}")
    slug = workspace_slug.strip() or await _get_slug()

    with p.open("rb") as fh:
        files = {"file": (p.name, fh, "application/octet-stream")}
        async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT) as client:
            resp = await client.post(
                f"{BASE_URL}/v1/document/upload",
                headers=_headers(),
                files=files,
                data={"addToWorkspaces": slug},
            )
    if resp.status_code != 200:
        raise _api_error("上传文档", resp)

    payload = resp.json()
    docs = payload.get("documents") or []
    locations = [d.get("location") for d in docs if isinstance(d, dict) and d.get("location")]
    return (
        f"上传成功：{p.name} → 工作区 {slug}\n"
        f"文档条目 {len(docs)} 个，location：{'、'.join(locations) or '（无）'}\n"
        f"原始响应：{payload}"
    )


# ---------- 能力 3：对话与检索问答 ----------
@mcp.tool(
    name="ask_workspace",
    description=(
        "基于 AnythingLLM 指定工作区的文档做 RAG 问答，返回回答与参考来源。"
        "question 为自然语言问题；workspace_slug 留空则用配置值或第一个工作区。"
    ),
    structured_output=False,
)
async def ask_workspace(question: str, workspace_slug: str = "") -> str:
    _check_config()
    slug = workspace_slug.strip() or await _get_slug()
    async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT) as client:
        resp = await client.post(
            f"{BASE_URL}/v1/workspace/{slug}/chat",
            headers=_headers(),
            json={"message": question, "mode": "query"},
        )
    if resp.status_code != 200:
        raise _api_error("工作区问答", resp)

    data = resp.json()
    answer = data.get("textResponse") or data.get("error") or "（无回答）"
    sources = data.get("sources", [])
    if sources:
        refs = "\n".join(f"- {s.get('title', '未命名')}" for s in sources)
        return f"{answer}\n\n参考来源：\n{refs}"
    return answer


def create_app():
    """返回 ASGI app，供 uvicorn 或测试挂载。"""
    return mcp.streamable_http_app(streamable_http_path=MCP_PATH)


if __name__ == "__main__":
    uvicorn.run(create_app(), host=MCP_HOST, port=MCP_PORT)
