import os

import httpx
from dotenv import load_dotenv
from mcp.server.fastmcp import FastMCP

load_dotenv()

BASE_URL = os.getenv("ANYTHINGLLM_BASE_URL", "http://localhost:3001").rstrip("/")
API_KEY = os.getenv("ANYTHINGLLM_API_KEY", "")
WORKSPACE_SLUG = os.getenv("ANYTHINGLLM_WORKSPACE_SLUG", "").strip()

mcp = FastMCP(
    "anythingllm",
    host=os.getenv("MCP_HOST", "0.0.0.0"),
    port=int(os.getenv("MCP_PORT", "8000")),
)

_workspace_slug: str | None = WORKSPACE_SLUG or None


async def _get_slug() -> str:
    """返回工作区 slug；未配置时自动取第一个工作区。"""
    global _workspace_slug
    if _workspace_slug:
        return _workspace_slug
    headers = {"Authorization": f"Bearer {API_KEY}"}
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.get(f"{BASE_URL}/v1/workspaces", headers=headers)
        resp.raise_for_status()
        workspaces = resp.json().get("workspaces", [])
    if not workspaces:
        raise RuntimeError("AnythingLLM 中没有任何工作区")
    _workspace_slug = workspaces[0]["slug"]
    return _workspace_slug


@mcp.tool()
async def ask_workspace(question: str) -> str:
    """基于 AnythingLLM 工作区的文档进行 AI 问答（RAG）。"""
    slug = await _get_slug()
    headers = {"Authorization": f"Bearer {API_KEY}"}
    async with httpx.AsyncClient(timeout=120) as client:
        resp = await client.post(
            f"{BASE_URL}/v1/workspace/{slug}/chat",
            headers=headers,
            json={"message": question, "mode": "query"},
        )
        resp.raise_for_status()
        data = resp.json()

    answer = data.get("textResponse") or data.get("error") or "（无回答）"
    sources = data.get("sources", [])
    if sources:
        refs = "\n".join(f"- {s.get('title', '未命名')}" for s in sources)
        return f"{answer}\n\n参考来源：\n{refs}"
    return answer


if __name__ == "__main__":
    mcp.run(transport="streamable-http")
