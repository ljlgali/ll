"""Runtime configuration, read from environment variables.

Environment variables (see `.env` for a documented template; set them in
the shell before launching `python -m pet_hospital_mcp`):

- PET_HOSPITAL_BASE_URL : upstream Go REST API base (default http://127.0.0.1:8080)
- MCP_HOST / MCP_PORT    : MCP server bind address (default 127.0.0.1:8000)
- MCP_ENDPOINT_PATH      : MCP JSON-RPC endpoint path (default /mcp)
- MCP_BACKEND_TIMEOUT    : upstream per-request timeout, seconds (default 5.0)
- MCP_BACKEND_RETRIES    : upstream retry attempts on transient errors (default 2)
"""

from __future__ import annotations

import os
from dataclasses import dataclass


def _env_str(name: str, default: str) -> str:
    value = os.environ.get(name)
    return value if value else default


def _env_int(name: str, default: int) -> int:
    raw = os.environ.get(name)
    if not raw:
        return default
    try:
        return int(raw)
    except ValueError:
        return default


def _env_float(name: str, default: float) -> float:
    raw = os.environ.get(name)
    if not raw:
        return default
    try:
        return float(raw)
    except ValueError:
        return default


@dataclass(frozen=True)
class Config:
    """Resolved runtime configuration."""

    base_url: str = _env_str("PET_HOSPITAL_BASE_URL", "http://127.0.0.1:8080")
    host: str = _env_str("MCP_HOST", "127.0.0.1")
    port: int = _env_int("MCP_PORT", 8000)
    endpoint_path: str = _env_str("MCP_ENDPOINT_PATH", "/mcp")
    backend_timeout: float = _env_float("MCP_BACKEND_TIMEOUT", 5.0)
    backend_retries: int = _env_int("MCP_BACKEND_RETRIES", 2)

    @classmethod
    def from_env(cls) -> Config:
        return cls()
