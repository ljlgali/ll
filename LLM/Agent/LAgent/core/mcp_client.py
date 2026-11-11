# core/mcp_client.py —— MCP Client 层（外部 MCP Server 接入）
# 职责：
#   1. 读取项目目录下的 .mcp.json，获得 MCP Server 连接信息（Streamable HTTP）
#   2. 用 MCP Python SDK 建立标准客户端连接，调用 list_tools() 发现工具
#   3. 把 MCP 工具转换成 OpenAI Function Calling Schema，动态注册进 Agent 工具集
#   4. 维护「对外工具名 -> (Server, 原始工具名)」映射，LLM 调用时转发并回传结果
#
# 线程模型：MCP SDK 是 asyncio 接口，而 Agent / TUI 是同步调用链。
# 这里在后台线程单独跑一个事件循环，连接常驻；主线程通过队列提交请求、
# 用 concurrent.futures.Future 取回结果，避免每次调用都重建连接。
import asyncio
import json
import re
import sys
import threading
import time
from concurrent.futures import Future
from dataclasses import dataclass, field
from pathlib import Path

# —— 兼容性处理 ——
# 本机虚拟环境根目录里存在一个练习用的 mcp.py，会遮蔽正式 mcp SDK 包。
# 这里把"目录下存在 mcp.py 文件"的 sys.path 条目移除，保证导入的是 SDK 包。
for _p in list(sys.path):
    if _p and (Path(_p) / "mcp.py").is_file():
        sys.path.remove(_p)

from mcp import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client
from mcp.client.streamable_http import streamable_http_client

PROJECT_ROOT = Path(__file__).resolve().parent.parent
CONNECT_TIMEOUT = 10       # 建立连接 + 发现工具的整体超时（秒）
CALL_TIMEOUT = 30          # 单次 MCP 工具调用超时（秒）
MAX_OUTPUT_CHARS = 8000   # 工具结果过长截断阈值（MCP 返回常含结构化数据，留足空间）

# 支持的传输类型（.mcp.json 里的 type 字段）
STREAMABLE_HTTP_TYPES = {"streamable_http", "streamablehttp", "http", "streamable-http"}
STDIO_TYPES = {"stdio", "local", "process"}


@dataclass
class MCPServer:
    """单个 MCP Server 的运行状态"""
    name: str
    url: str = ""
    command: str = ""                           # stdio 传输：可执行程序
    args: list = field(default_factory=list)    # stdio 传输：命令行参数
    env: dict = field(default_factory=dict)     # stdio 传输：额外环境变量
    queue: asyncio.Queue | None = None
    status: str = "pending"                     # pending / connected / failed
    error: str = ""
    tools: list = field(default_factory=list)   # 原始 mcp.types.Tool 列表

    @property
    def transport(self) -> str:
        return "stdio" if self.command else "streamable_http"

    @property
    def endpoint(self) -> str:
        """日志/状态里展示的连接目标：stdio 显示命令行，http 显示 URL"""
        if self.command:
            return " ".join([self.command] + [str(a) for a in self.args])
        return self.url


def load_mcp_config(path: str | Path | None = None) -> tuple[dict, str]:
    """读取 .mcp.json 配置。
    查找顺序：显式 path -> 当前工作目录 -> 项目根目录（main.py 所在目录）。
    返回 (servers 字典, 错误说明)；成功时错误说明为空字符串。
    """
    if path:
        candidates = [Path(path)]
    else:
        candidates = [Path.cwd() / ".mcp.json", PROJECT_ROOT / ".mcp.json"]

    cfg_path = next((c for c in candidates if c.is_file()), None)
    if cfg_path is None:
        return {}, "未找到 .mcp.json 配置文件"

    try:
        data = json.loads(cfg_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        return {}, f".mcp.json 格式错误：{e}"
    except Exception as e:
        return {}, f"读取 .mcp.json 失败：{e}"

    servers = data.get("mcpServers") or {}
    if not isinstance(servers, dict) or not servers:
        return {}, ".mcp.json 中没有配置任何 MCP Server（缺少 mcpServers）"
    return servers, ""


def _sanitize(name: str) -> str:
    """把任意名称转成合法的 Function Calling 工具名（字母/数字/下划线/连字符）"""
    cleaned = re.sub(r"[^a-zA-Z0-9_-]", "_", name or "")
    return (cleaned or "mcp")[:64]


def _inline_refs(node, defs: dict, depth: int = 0):
    """把 JSON Schema 里的 $ref 就地展开成 $defs 定义，
    并去掉 LLM 用不上的字段（title / default:null / $defs 等）。
    Pydantic 生成的 schema 大量使用 $ref，直接塞给模型容易解析失败。"""
    if depth > 6:            # 防御循环引用
        return node
    if isinstance(node, list):
        return [_inline_refs(i, defs, depth + 1) for i in node]
    if not isinstance(node, dict):
        return node

    ref = node.get("$ref")
    if isinstance(ref, str) and ref.startswith("#/$defs/"):
        target = defs.get(ref.split("/")[-1])
        if isinstance(target, dict):
            merged = _inline_refs(target, defs, depth + 1)
            # $ref 同级可能带 description 等覆盖字段
            for k, v in node.items():
                if k != "$ref":
                    merged.setdefault(k, v)
            return merged

    cleaned = {}
    for k, v in node.items():
        if k in ("$defs", "$schema", "title", "additionalProperties"):
            continue
        if k == "default" and v is None:
            continue
        cleaned[k] = _inline_refs(v, defs, depth + 1)
    return cleaned


def _clean_schema(schema: dict | None) -> dict:
    """清洗 MCP 的 inputSchema，转成 OpenAI 能接受的 parameters"""
    if not isinstance(schema, dict) or not schema:
        return {"type": "object", "properties": {}}
    defs = schema.get("$defs") or {}
    params = _inline_refs(schema, defs)
    if not isinstance(params, dict):
        return {"type": "object", "properties": {}}
    params.setdefault("type", "object")
    params.setdefault("properties", {})
    return params


def _describe_error(e: BaseException) -> str:
    """把 anyio/asyncio 的 ExceptionGroup 拆到最内层，给出可读的错误原因"""
    cur = e
    while True:
        subs = getattr(cur, "exceptions", None)
        if subs:
            cur = subs[0]
            continue
        break
    detail = str(cur).strip() or type(cur).__name__
    return f"{type(cur).__name__}: {detail}" if str(cur).strip() else detail


def _format_result(res) -> str:
    """把 MCP 的 CallToolResult 统一转成给 LLM 看的文本：
    文本块、结构化数据、错误标记都要处理"""
    parts = []
    for block in getattr(res, "content", None) or []:
        text = getattr(block, "text", None)
        if text:
            parts.append(text)
            continue
        if getattr(block, "type", None) == "image":
            parts.append("[MCP 返回了一张图片，文本界面已省略]")
            continue
        try:
            parts.append(json.dumps(block.model_dump(exclude_none=True), ensure_ascii=False))
        except Exception:
            parts.append(str(block))

    text = "\n".join(parts).strip()
    text_is_json = False
    # 纯 JSON 文本去掉缩进空白，减少冗余 token（内容不变，模型同样可读）
    if text.startswith(("{", "[")):
        try:
            text = json.dumps(json.loads(text), ensure_ascii=False, separators=(",", ":"))
            text_is_json = True
        except Exception:
            pass
    structured = (getattr(res, "structured_content", None)
                  or getattr(res, "structuredContent", None))
    # 文本块已经就是同一份 JSON 时，不再重复追加结构化数据
    if structured and not text_is_json:
        text += "\n【结构化数据】\n" + json.dumps(structured, ensure_ascii=False, separators=(",", ":"))
    if not text:
        text = "（MCP 工具无返回内容）"
    if getattr(res, "is_error", None) or getattr(res, "isError", None):
        text = "MCP 工具返回错误：" + text
    if len(text) > MAX_OUTPUT_CHARS:
        text = text[:MAX_OUTPUT_CHARS] + f"\n...（结果过长，已截断：原文 {len(text)} 字符）"
    return text


class MCPManager:
    """MCP Server 集合管理器：连接、发现、注册、调用"""

    def __init__(self, config_path: str | Path | None = None):
        self.config_path = config_path
        self.servers: dict[str, MCPServer] = {}
        self.errors: list[str] = []                      # 配置/连接层面的错误说明
        self.schemas: list[dict] = []                    # 供 LLM 的工具 Schema
        self.tool_map: dict[str, tuple[str, str]] = {}   # 对外名 -> (Server名, 原工具名)
        self._loop: asyncio.AbstractEventLoop | None = None
        self._thread: threading.Thread | None = None
        self._closing = False

    # ---------- 对外状态 ----------
    @property
    def connected_servers(self) -> list[MCPServer]:
        return [s for s in self.servers.values() if s.status == "connected"]

    def has_tool(self, name: str) -> bool:
        return name in self.tool_map

    def prompt_block(self) -> str:
        """给 System Prompt 的 MCP 说明段落；没有可用工具时返回空串"""
        if not self.schemas:
            return ""
        lines = ["\n\n已连接的外部 MCP Server（其工具与本地工具一样可直接调用）："]
        for server in self.connected_servers:
            exposed = [n for n, (sn, _) in self.tool_map.items() if sn == server.name]
            lines.append(f"- `{server.name}`：{'、'.join(exposed)}")
        lines.append("调用 MCP 工具时按工具声明的参数传递，执行结果由系统自动回传；"
                     "若工具返回错误信息，如实转告用户，不要编造结果。")
        return "".join(lines)

    def describe(self) -> str:
        """/mcp 命令与欢迎信息用的状态摘要"""
        if not self.servers and not self.errors:
            return "未配置 MCP Server"
        lines = []
        for err in self.errors:
            lines.append(f"⚠ {err}")
        for server in self.servers.values():
            if server.status == "connected":
                names = [n for n, (sn, _) in self.tool_map.items() if sn == server.name]
                lines.append(f"OK {server.name}（{server.transport}: {server.endpoint}）"
                             f"工具 {len(names)} 个：{'、'.join(names)}")
            else:
                lines.append(f"FAIL {server.name}（{server.transport}: {server.endpoint}）"
                             f"连接失败：{server.error or '未知原因'}")
        return "\n".join(lines)

    # ---------- 生命周期 ----------
    def start(self) -> None:
        """启动后台事件循环，并发连接所有 MCP Server 并发现工具"""
        if self._loop is not None:
            return
        servers_cfg, err = load_mcp_config(self.config_path)
        if err:
            self.errors.append(err)
            return

        self._ensure_loop()
        pending: list[tuple[MCPServer, threading.Event]] = []
        for name, cfg in servers_cfg.items():
            if not isinstance(cfg, dict):
                self.errors.append(f"MCP Server「{name}」配置格式错误，已跳过")
                continue
            stype = str(cfg.get("type") or "streamable_http").lower()
            url = str(cfg.get("url") or "").strip()
            command = str(cfg.get("command") or "").strip()
            raw_args = cfg.get("args") or []
            server_args = [str(a) for a in raw_args] if isinstance(raw_args, list) else []
            raw_env = cfg.get("env") or {}
            server_env = {str(k): str(v) for k, v in raw_env.items()} if isinstance(raw_env, dict) else {}

            # —— 传输类型判定：stdio 用 command，HTTP 用 url ——
            if stype in STDIO_TYPES or (command and stype not in STREAMABLE_HTTP_TYPES):
                server = MCPServer(name=name, command=command, args=server_args, env=server_env)
                self.servers[name] = server
                if not command:
                    server.status = "failed"
                    server.error = "stdio 类型缺少 command 字段"
                    continue
                server.queue = self._make_queue()
                evt = threading.Event()
                asyncio.run_coroutine_threadsafe(self._serve_stdio(server, evt), self._loop)
                pending.append((server, evt))
                continue

            server = MCPServer(name=name, url=url)
            self.servers[name] = server
            if stype not in STREAMABLE_HTTP_TYPES:
                server.status = "failed"
                server.error = (f"不支持的类型 {stype}"
                                f"（支持 streamable_http / http / stdio）")
                continue
            if not url.lower().startswith(("http://", "https://")):
                server.status = "failed"
                server.error = "url 无效（需以 http:// 或 https:// 开头）"
                continue
            server.queue = self._make_queue()
            evt = threading.Event()
            asyncio.run_coroutine_threadsafe(self._serve(server, evt), self._loop)
            pending.append((server, evt))

        # 等待所有 Server 就绪（整体不超过 CONNECT_TIMEOUT）
        deadline = time.time() + CONNECT_TIMEOUT
        for server, evt in pending:
            remain = max(0.5, deadline - time.time())
            if not evt.wait(remain):
                server.status = "failed"
                server.error = f"连接超时（{CONNECT_TIMEOUT} 秒）"
        self._register_tools()

    def stop(self) -> None:
        """关闭连接并停止后台事件循环"""
        self._closing = True
        for server in self.servers.values():
            if server.queue is not None and self._loop is not None:
                try:
                    self._loop.call_soon_threadsafe(server.queue.put_nowait, None)
                except Exception:
                    pass
        if self._loop is not None:
            self._loop.call_soon_threadsafe(self._loop.stop)
        if self._thread is not None:
            self._thread.join(timeout=3)

    def _make_queue(self) -> asyncio.Queue:
        """在后台事件循环里创建队列（asyncio.Queue 需绑定该循环）"""
        fut: Future = Future()
        holder = {}

        async def _create():
            holder["q"] = asyncio.Queue()
            fut.set_result(holder["q"])

        asyncio.run_coroutine_threadsafe(_create(), self._loop)
        return fut.result(timeout=5)

    def _ensure_loop(self) -> None:
        if self._thread is not None:
            return
        self._loop = asyncio.new_event_loop()

        def run():
            asyncio.set_event_loop(self._loop)
            self._loop.run_forever()

        self._thread = threading.Thread(target=run, daemon=True, name="mcp-loop")
        self._thread.start()

    # ---------- 后台协程：常驻连接 ----------
    async def _serve(self, server: MCPServer, ready: threading.Event) -> None:
        """一个 Server 一个常驻任务：先连接 + 发现工具，再循环处理调用请求"""
        try:
            async with streamable_http_client(server.url) as streams:
                read, write = streams[0], streams[1]
                async with ClientSession(read, write) as session:
                    await session.initialize()
                    result = await session.list_tools()
                    server.tools = list(result.tools or [])
                    server.status = "connected"
                    ready.set()
                    while not self._closing:
                        item = await server.queue.get()
                        if item is None:
                            break
                        cfut, tool_name, args = item
                        if cfut.set_running_or_notify_cancel() is False:
                            continue
                        try:
                            res = await session.call_tool(tool_name, args)
                            cfut.set_result(_format_result(res))
                        except Exception as e:
                            cfut.set_result(
                                f"错误：调用 MCP 工具 {tool_name} 失败 -> "
                                f"{type(e).__name__}: {e}"
                            )
        except Exception as e:
            server.status = "failed"
            server.error = _describe_error(e)
        finally:
            ready.set()

    async def _serve_stdio(self, server: MCPServer, ready: threading.Event) -> None:
        """stdio 传输：拉起本地子进程，用 stdin/stdout 管道承载 MCP 协议。
        stdin/stdout 即传输通道，不需要 HTTP 端点。"""
        try:
            params = StdioServerParameters(
                command=server.command,
                args=server.args,
                env=server.env or None,
            )
            async with stdio_client(params) as streams:
                read, write = streams[0], streams[1]
                async with ClientSession(read, write) as session:
                    await session.initialize()
                    result = await session.list_tools()
                    server.tools = list(result.tools or [])
                    server.status = "connected"
                    ready.set()
                    while not self._closing:
                        item = await server.queue.get()
                        if item is None:
                            break
                        cfut, tool_name, args = item
                        if cfut.set_running_or_notify_cancel() is False:
                            continue
                        try:
                            res = await session.call_tool(tool_name, args)
                            cfut.set_result(_format_result(res))
                        except Exception as e:
                            cfut.set_result(
                                f"错误：调用 MCP 工具 {tool_name} 失败 -> "
                                f"{type(e).__name__}: {e}"
                            )
        except FileNotFoundError as e:
            server.status = "failed"
            server.error = f"stdio 启动失败：找不到命令 {server.command}（{e}）"
        except Exception as e:
            server.status = "failed"
            server.error = f"stdio 连接失败：{_describe_error(e)}"
        finally:
            ready.set()

    # ---------- 工具注册（名称冲突时加 Server 前缀） ----------
    def _register_tools(self) -> None:
        from core.tools import TOOLS     # 延迟导入，避免循环依赖

        used = {t["function"]["name"] for t in TOOLS}
        self.schemas = []
        self.tool_map = {}

        for server in self.connected_servers:
            for tool in server.tools:
                original = tool.name
                exposed = original
                # 与本地工具或其它 Server 的工具重名 -> 加 Server 名称前缀；
                # 名称不符合 Function Calling 规范时同样做规范化
                if exposed in used or not re.fullmatch(r"[a-zA-Z0-9_-]{1,64}", exposed):
                    exposed = _sanitize(f"{server.name}__{original}")
                used.add(exposed)
                self.tool_map[exposed] = (server.name, original)

                desc = (tool.description or "").strip() or f"{server.name} 提供的 MCP 工具"
                self.schemas.append({
                    "type": "function",
                    "function": {
                        "name": exposed,
                        "description": f"[MCP/{server.name}] {desc}",
                        "parameters": _clean_schema(tool.input_schema),
                    }
                })

    # ---------- 工具调用 ----------
    def call_tool(self, exposed_name: str, args: dict | None) -> str:
        """LLM 发起 MCP 工具调用时，转发到对应 Server 并返回文本结果"""
        entry = self.tool_map.get(exposed_name)
        if entry is None:
            return f"错误：未知的 MCP 工具 {exposed_name}"
        server_name, original = entry
        server = self.servers.get(server_name)
        if server is None or server.status != "connected" or server.queue is None:
            reason = server.error if server and server.error else "未连接"
            return f"错误：MCP Server {server_name} 当前不可用（{reason}）"

        cfut: Future = Future()
        try:
            self._loop.call_soon_threadsafe(
                server.queue.put_nowait, (cfut, original, args or {})
            )
        except Exception as e:
            return f"错误：提交 MCP 调用失败 -> {e}"
        try:
            return cfut.result(timeout=CALL_TIMEOUT)
        except TimeoutError:
            return f"错误：MCP 工具 {exposed_name} 调用超时（{CALL_TIMEOUT} 秒）"
        except Exception as e:
            return f"错误：MCP 工具 {exposed_name} 调用失败 -> {type(e).__name__}: {e}"
