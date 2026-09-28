"""MCPServer assembly for the Pet Hospital MCP adapter.

Builds an `MCPServer` (SDK 2.x) with the `list_pets` tool registered, a `/health`
custom route, and a stateless Streamable HTTP app at `/mcp`. The 2026-07-28
modern, sessionless request path is selected automatically by the
`MCP-Protocol-Version` request header — no `initialize`, no `Mcp-Session-Id`,
no server-side session storage.
"""

from __future__ import annotations

from typing import Any

from mcp.server.mcpserver import MCPServer
from mcp.types.version import LATEST_MODERN_VERSION
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.applications import Starlette

from pet_hospital_mcp import __version__
from pet_hospital_mcp.config import Config
from pet_hospital_mcp.logging_config import configure_logging
from pet_hospital_mcp.rest_client import PetHospitalClient
from pet_hospital_mcp.tools.list_pets import register_list_pets

# The MCP protocol version this server speaks (stateless era).
PROTOCOL_VERSION = LATEST_MODERN_VERSION  # "2026-07-28"


def create_mcp_server(client: PetHospitalClient) -> MCPServer:
    """Construct an MCPServer with the list_pets tool and /health route."""
    configure_logging()

    mcp = MCPServer(
        name="pet-hospital-mcp",
        title="Pet Hospital MCP",
        description=(
            "Stateless MCP 2026-07-28 adapter exposing the Go Pet Hospital "
            "REST API. Currently exposes one tool: list_pets."
        ),
        version=__version__,
    )

    register_list_pets(mcp, client)

    @mcp.custom_route("/health", methods=["GET"])
    async def health(request: Request) -> JSONResponse:
        """Liveness probe; the Go backend is NOT queried here."""
        return JSONResponse(
            {
                "status": "ok",
                "service": "pet-hospital-mcp",
                "version": __version__,
                "protocol_version": PROTOCOL_VERSION,
            }
        )

    return mcp


def create_app(
    client: PetHospitalClient | None = None,
    *,
    config: Config | None = None,
    streamable_http_path: str = "/mcp",
) -> Starlette:
    """Return the ASGI app (Starlette) serving MCP at `/mcp` + `/health`.

    Pass a `client` with a mock transport for tests; in production the client
    is built from environment configuration.
    """
    cfg = config or Config.from_env()
    if client is None:
        client = PetHospitalClient.from_config(cfg)
    mcp = create_mcp_server(client)
    return mcp.streamable_http_app(streamable_http_path=streamable_http_path)
