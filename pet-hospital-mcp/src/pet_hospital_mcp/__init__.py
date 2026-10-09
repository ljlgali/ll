"""Pet Hospital MCP — a stateless MCP 2026-07-28 adapter over the Go Pet Hospital REST API.

Only the `list_pets` tool is implemented in this stage. See README.md for usage.
"""

# __version__ must be defined before importing submodules that reference it.
__version__ = "1.0.0"

from pet_hospital_mcp.config import Config
from pet_hospital_mcp.server import create_app, create_mcp_server

__all__ = ["Config", "create_app", "create_mcp_server", "__version__"]
