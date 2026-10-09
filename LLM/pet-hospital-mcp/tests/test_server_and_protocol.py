"""Server & stateless-protocol tests.

Covers (per prompt):
- /health endpoint
- tool registration, name, and JSON Schema
- SDK 2.x stateless connection flow:
    * no legacy `initialize` handshake sent
    * no `Mcp-Session-Id` required/returned
    * `server/discover` and `tools/list` and `tools/call` over the 2026-07-28
      Streamable HTTP endpoint
- list_pets discoverable and callable (success + unified validation error)
"""

from __future__ import annotations

import json
from contextlib import asynccontextmanager
from typing import Any, AsyncIterator

import httpx
import pytest
from asgi_lifespan import LifespanManager

from mcp import Client
from mcp.client.streamable_http import streamable_http_client

from pet_hospital_mcp.server import PROTOCOL_VERSION, create_app


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------
# Base URL uses a loopback host WITH a port so the Host header sent through
# ASGITransport matches the SDK's default DNS-rebinding allow-list
# (["127.0.0.1:*", "localhost:*", "[::1]:*"]) — the wildcard `host:*` only
# matches a Host that has a colon-port suffix. Without a port the request is
# rejected with 421 Misdirected Request.
_BASE_URL = "http://localhost:8080"

# Modern 2026-07-28 envelope keys carried inside `params._meta` of every
# request, alongside the `MCP-Protocol-Version` and `MCP-Method` headers.
_PROTOCOL_VERSION_META_KEY = "io.modelcontextprotocol/protocolVersion"
_CLIENT_CAPABILITIES_META_KEY = "io.modelcontextprotocol/clientCapabilities"


@asynccontextmanager
async def _lifespan_http(app: Any) -> AsyncIterator[httpx.AsyncClient]:
    """Run the ASGI lifespan (so the Streamable HTTP session manager's task
    group starts) then yield an httpx client bound to the app via ASGITransport.
    ASGITransport alone does NOT run lifespan, which is why this is required.
    """
    async with LifespanManager(app):
        yield httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app),
            base_url=_BASE_URL,
        )


def _modern_headers(method: str, *, name: str | None = None) -> dict[str, str]:
    """Headers required by the 2026-07-28 modern request path.

    For name-bearing methods (`tools/call`, `prompts/get`, `resources/read`)
    the SDK also requires `MCP-Name` to equal `params.name` — pass `name=`
    for those. See `NAME_BEARING_METHODS` in `mcp.shared.inbound`.
    """
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json, text/event-stream",
        "MCP-Protocol-Version": PROTOCOL_VERSION,
        "MCP-Method": method,
    }
    if name is not None:
        headers["MCP-Name"] = name
    return headers


def _modern_params(method: str, *, extra: dict | None = None) -> dict:
    """Build `params` for a modern JSON-RPC request, carrying the `_meta`
    envelope the 2026-07-28 era router requires (`protocolVersion` +
    `clientCapabilities`; `clientInfo` is optional and omitted here).
    """
    params: dict[str, Any] = {
        "_meta": {
            _PROTOCOL_VERSION_META_KEY: PROTOCOL_VERSION,
            _CLIENT_CAPABILITIES_META_KEY: {},
        }
    }
    if extra:
        params.update(extra)
    return params


def _success_handler():
    """Backend handler returning a single-pet list for any /api/v1/pets call."""
    pet = {
        "id": "PET-1", "name": "旺财", "species": "犬", "breed": "金毛",
        "gender": "公", "ageMonths": 36, "color": "黄", "chipNo": "CHIP-1",
        "ownerName": "张三", "ownerPhone": "13800001111", "ownerAddr": "北京市",
        "doctor": "李医生", "disease": "健康", "status": "待就诊",
        "allergy": "无", "note": "", "records": None, "charges": None,
        "totalCost": 100.0, "visitCount": 0,
        "createdAt": "2026-09-15T13:50:11+08:00", "updatedAt": "2026-09-15T13:50:11+08:00",
    }
    data = {"items": [pet], "total": 1, "page": 1, "pageSize": 1, "totalPages": 1, "totalCost": 100.0}
    body = json.dumps({"code": 200, "message": "ok", "data": data, "time": "t"}, ensure_ascii=False).encode()

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=body)

    return handler


def _parse_response(resp: httpx.Response) -> dict:
    """Parse a Streamable HTTP response that may be a single JSON object or SSE."""
    ct = resp.headers.get("content-type", "")
    text = resp.text
    if "text/event-stream" in ct:
        # last `data:` line holds the JSON-RPC response
        data_lines = [
            line[5:].strip() for line in text.splitlines() if line.startswith("data:")
        ]
        assert data_lines, f"no SSE data lines: {text!r}"
        return json.loads(data_lines[-1])
    return json.loads(text)


# ---------------------------------------------------------------------------
# /health
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_health_endpoint(make_client):
    app = create_app(client=make_client(_success_handler()))
    async with _lifespan_http(app) as http:
        resp = await http.get("/health")
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "ok"
        assert body["service"] == "pet-hospital-mcp"
        assert body["protocol_version"] == PROTOCOL_VERSION == "2026-07-28"


# ---------------------------------------------------------------------------
# stateless wire behavior: no Mcp-Session-Id
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_raw_post_returns_no_session_id(make_client):
    """A raw 2026-07-28 POST (tools/list) must NOT return an Mcp-Session-Id header."""
    app = create_app(client=make_client(_success_handler()))
    method = "tools/list"
    async with _lifespan_http(app) as http:
        resp = await http.post(
            "/mcp",
            headers=_modern_headers(method),
            json={
                "jsonrpc": "2.0", "id": 1, "method": method,
                "params": _modern_params(method),
            },
        )
        assert resp.status_code == 200, f"body={resp.text!r}"
        # The stateless 2026-07-28 path never sets Mcp-Session-Id.
        assert "mcp-session-id" not in {k.lower() for k in resp.headers.keys()}


@pytest.mark.asyncio
async def test_no_legacy_initialize_required(make_client):
    """A tools/call without any prior `initialize` must succeed (stateless)."""
    app = create_app(client=make_client(_success_handler()))
    method = "tools/call"
    async with _lifespan_http(app) as http:
        resp = await http.post(
            "/mcp",
            headers=_modern_headers(method, name="list_pets"),
            json={
                "jsonrpc": "2.0", "id": 2, "method": method,
                "params": _modern_params(
                    method,
                    extra={
                        "name": "list_pets",
                        # Tool's input model is a single Pydantic param `args`
                        # (permissive, extra="allow"), so all 14 Go query
                        # parameters are nested under `args` on the wire.
                        "arguments": {"args": {"species": "犬"}},
                    },
                ),
            },
        )
        assert resp.status_code == 200, f"body={resp.text!r}"
        parsed = _parse_response(resp)
        assert parsed.get("result") is not None
        # Modern wire key is `isError`; absence or False both indicate success.
        assert parsed["result"].get("isError") in (None, False)


# ---------------------------------------------------------------------------
# SDK client: discover, list tools, call tool
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_sdk_client_discovers_and_lists_tools(make_client):
    app = create_app(client=make_client(_success_handler()))
    async with _lifespan_http(app) as http:
        # Passing the streamable_http_client context manager as `server=` makes
        # the high-level Client treat it as a user-supplied Transport (the `else`
        # branch in __post_init__), and `mode="auto"` (default) probes
        # `server/discover` on enter — populating protocol_version and
        # server_capabilities. No `initialize` handshake is sent.
        transport = streamable_http_client(f"{_BASE_URL}/mcp", http_client=http)
        async with Client(transport) as client:
            assert client.protocol_version == "2026-07-28"
            assert client.server_capabilities is not None

            result = await client.list_tools()
            names = [t.name for t in result.tools]
            assert names == ["list_pets"]


@pytest.mark.asyncio
async def test_tool_input_schema_has_all_fields(make_client):
    app = create_app(client=make_client(_success_handler()))
    async with _lifespan_http(app) as http:
        transport = streamable_http_client(f"{_BASE_URL}/mcp", http_client=http)
        async with Client(transport) as client:
            result = await client.list_tools()
            tool = result.tools[0]
            assert tool.name == "list_pets"
            assert tool.description and "GET /api/v1/pets" in tool.description
            # Client-side `Tool.input_schema` is the input schema (wire key
            # `inputSchema`); the tool's permissive `args: ListPetsArgs` param
            # surfaces as a single `args` property whose sub-properties are
            # the 14 Go query parameters. Pydantic factors the nested model
            # out to `$defs` and surfaces it as a `$ref`, so resolve the ref
            # before inspecting its `properties`.
            schema = tool.input_schema
            props = set(schema.get("properties", {}).keys())
            assert "args" in props, f"expected `args` property; got {props}"
            args_schema = schema["properties"]["args"]
            args_schema = _resolve_ref(args_schema, schema)
            args_props = set(args_schema.get("properties", {}).keys())
            expected = {
                "q", "name", "ownerName", "ownerPhone", "species", "doctor",
                "disease", "status", "min", "max", "sortBy", "order", "page", "pageSize",
            }
            assert expected.issubset(args_props), f"missing: {expected - args_props}"
            # structured output schema is advertised (success model)
            assert tool.output_schema is not None
            out_props = set(tool.output_schema.get("properties", {}).keys())
            assert {"items", "total", "page", "pageSize", "totalPages", "totalCost"}.issubset(out_props)


def _resolve_ref(node: dict, root: dict) -> dict:
    """Follow a single `$ref` (e.g. `{"$ref": "#/$defs/ListPetsArgs"`) to its
    target in the same schema document. Returns `node` unchanged if no ref."""
    ref = node.get("$ref")
    if not ref:
        return node
    assert ref.startswith("#/"), f"unsupported ref kind: {ref!r}"
    cursor: Any = root
    for part in ref[2:].split("/"):
        cursor = cursor[part]
    return cursor


@pytest.mark.asyncio
async def test_sdk_client_call_list_pets_success(make_client):
    app = create_app(client=make_client(_success_handler()))
    async with _lifespan_http(app) as http:
        transport = streamable_http_client(f"{_BASE_URL}/mcp", http_client=http)
        async with Client(transport) as client:
            # Arguments are nested under `args` (the permissive Pydantic param).
            result = await client.call_tool(
                "list_pets",
                {"args": {"species": "犬", "page": 1, "pageSize": 10}},
            )
            # 2.x uses snake_case attribute `is_error` (wire key `isError`).
            assert result.is_error is False or result.is_error is None
            # Structured output lands in `content[0].text` as JSON.
            text = result.content[0].text if result.content else ""
            payload = json.loads(text)
            assert payload["total"] == 1
            assert payload["items"][0]["id"] == "PET-1"


@pytest.mark.asyncio
async def test_sdk_client_validation_error_returns_unified_envelope(make_client):
    """A bad enum must produce a failed result with the unified error JSON."""
    app = create_app(client=make_client(_success_handler()))
    async with _lifespan_http(app) as http:
        transport = streamable_http_client(f"{_BASE_URL}/mcp", http_client=http)
        async with Client(transport) as client:
            result = await client.call_tool("list_pets", {"args": {"species": "龙"}})
            assert result.is_error is True
            text = result.content[0].text
            envelope = json.loads(text)
            assert envelope["error"]["code"] == "VALIDATION_ERROR"
            # no raw pydantic / python stack leaked
            assert "ValidationError" not in text
            assert "Error executing tool" not in text


@pytest.mark.asyncio
async def test_sdk_client_validation_error_unknown_field(make_client):
    app = create_app(client=make_client(_success_handler()))
    async with _lifespan_http(app) as http:
        transport = streamable_http_client(f"{_BASE_URL}/mcp", http_client=http)
        async with Client(transport) as client:
            # `args` is permissive (extra="allow") so `bogus` reaches the tool
            # body; the strict `ListPetsInput` (extra="forbid") then rejects it.
            result = await client.call_tool("list_pets", {"args": {"bogus": "x"}})
            assert result.is_error is True
            envelope = json.loads(result.content[0].text)
            assert envelope["error"]["code"] == "VALIDATION_ERROR"


@pytest.mark.asyncio
async def test_sdk_client_backend_error_surfaces_unified(make_client):
    """A 5xx upstream becomes a failed result with BACKEND_API_ERROR."""
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, content=json.dumps({"code": 500, "message": "boom", "time": "t"}).encode())

    app = create_app(client=make_client(handler, retries=0))
    async with _lifespan_http(app) as http:
        transport = streamable_http_client(f"{_BASE_URL}/mcp", http_client=http)
        async with Client(transport) as client:
            result = await client.call_tool("list_pets", {"args": {"species": "犬"}})
            assert result.is_error is True
            envelope = json.loads(result.content[0].text)
            assert envelope["error"]["code"] == "BACKEND_API_ERROR"
