"""Shared pytest fixtures.

The Go backend is NEVER hit — every PetHospitalClient uses an httpx MockTransport
whose handler is per-test. The MCP ASGI app is driven through httpx ASGITransport.
"""

from __future__ import annotations

import json
from contextlib import asynccontextmanager
from typing import Any, AsyncIterator, Callable

import httpx
import pytest
from asgi_lifespan import LifespanManager

from pet_hospital_mcp.rest_client import PetHospitalClient
from pet_hospital_mcp.server import create_app


def _envelope(code: int = 200, message: str = "ok", data: Any = None) -> bytes:
    return json.dumps(
        {"code": code, "message": message, "data": data, "time": "2026-09-17T10:00:00+08:00"},
        ensure_ascii=False,
    ).encode("utf-8")


def make_pet(
    *,
    id: str = "PET-000001",
    name: str = "旺财",
    species: str = "犬",
    records: list | None = None,
    charges: list | None = None,
    totalCost: float = 100.0,
) -> dict[str, Any]:
    """A minimal pet dict; records/charges default to None to exercise null handling."""
    return {
        "id": id,
        "name": name,
        "species": species,
        "breed": "金毛",
        "gender": "公",
        "ageMonths": 36,
        "color": "黄色",
        "chipNo": "CHIP-1",
        "ownerName": "张三",
        "ownerPhone": "13800001111",
        "ownerAddr": "北京市朝阳区",
        "doctor": "李医生",
        "disease": "健康",
        "status": "待就诊",
        "allergy": "无",
        "note": "",
        "records": records,
        "charges": charges,
        "totalCost": totalCost,
        "visitCount": 0,
        "createdAt": "2026-09-15T13:50:11+08:00",
        "updatedAt": "2026-09-15T13:50:11+08:00",
    }


def make_list_data(pets: list[dict] | None = None, *, total: int = 1, totalCost: float = 100.0) -> dict[str, Any]:
    pets = pets if pets is not None else [make_pet()]
    return {
        "items": pets,
        "total": total,
        "page": 1,
        "pageSize": len(pets),
        "totalPages": max(1, (total + len(pets) - 1) // max(1, len(pets))),
        "totalCost": totalCost,
    }


@pytest.fixture
def make_backend() -> Callable[..., httpx.MockTransport]:
    """Return a factory that builds a MockTransport from a handler callable."""

    def _factory(handler: Callable[[httpx.Request], httpx.Response]) -> httpx.MockTransport:
        return httpx.MockTransport(handler)

    return _factory


@pytest.fixture
def make_client(make_backend) -> Callable[..., PetHospitalClient]:
    """Build a PetHospitalClient backed by a mock transport."""

    def _factory(
        handler: Callable[[httpx.Request], httpx.Response],
        *,
        base_url: str = "http://127.0.0.1:8080",
        timeout: float = 5.0,
        retries: int = 2,
    ) -> PetHospitalClient:
        transport = make_backend(handler)
        return PetHospitalClient(
            base_url=base_url, timeout=timeout, retries=retries, transport=transport
        )

    return _factory


@pytest.fixture
def make_app(make_client) -> Callable[..., tuple[Any, PetHospitalClient]]:
    """Build the MCP ASGI app with a mocked backend; return (app, client)."""

    def _factory(
        handler: Callable[[httpx.Request], httpx.Response],
    ) -> tuple[Any, PetHospitalClient]:
        client = make_client(handler)
        app = create_app(client=client)
        return app, client

    return _factory


@pytest.fixture
def asgi_client():
    """An async-context-manager factory that runs the app's lifespan and yields
    an httpx client over ASGITransport. Running lifespan is required because
    the Streamable HTTP session manager initializes its task group in startup.

    The base_url uses a loopback host WITH a port so the Host header matches
    the SDK's default DNS-rebinding allow-list (["127.0.0.1:*", "localhost:*",
    "[::1]:*"]) — the wildcard `host:*` only matches a Host that has a port
    suffix; without one, the request is rejected with 421 Misdirected Request.
    """

    @asynccontextmanager
    async def _for(app: Any) -> AsyncIterator[httpx.AsyncClient]:
        async with LifespanManager(app):
            yield httpx.AsyncClient(
                transport=httpx.ASGITransport(app=app),
                base_url="http://localhost:8080",
            )

    return _for


@pytest.fixture
def envelope():
    return _envelope


@pytest.fixture
def pet_factory():
    return make_pet


@pytest.fixture
def list_data_factory():
    return make_list_data
