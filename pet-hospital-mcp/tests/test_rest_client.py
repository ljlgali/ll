"""Backend-interaction tests for PetHospitalClient.list_pets.

Covers: param forwarding (path + all filters/sort/paging), 4xx/5xx, timeout,
connection error, invalid JSON, and response-model mismatch.
"""

from __future__ import annotations

import json

import httpx
import pytest

from pet_hospital_mcp.errors import (
    BACKEND_API_ERROR,
    BACKEND_INVALID_RESPONSE,
    BACKEND_TIMEOUT,
    BACKEND_UNAVAILABLE,
    PetHospitalError,
)
from pet_hospital_mcp.tools.list_pets import ListPetsInput


@pytest.mark.asyncio
async def test_normal_call_forwards_all_params_and_path(make_client, list_data_factory, envelope):
    captured: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["path"] = request.url.path
        captured["params"] = dict(request.url.params)
        return httpx.Response(200, content=envelope(200, "ok", list_data_factory()))

    client = make_client(handler)
    try:
        params = ListPetsInput(
            q="肠胃炎",
            name="旺财",
            ownerName="张三",
            ownerPhone="13800001111",
            species="犬",
            doctor="李医生",
            disease="骨折",
            status="待就诊",
            min=100.0,
            max=5000.0,
            sortBy="totalCost",
            order="desc",
            page=2,
            pageSize=15,
        )
        result = await client.list_pets(params)
    finally:
        await client.aclose()

    assert captured["path"] == "/api/v1/pets"
    # every supplied param is forwarded, camelCase, unchanged
    assert captured["params"] == {
        "q": "肠胃炎",
        "name": "旺财",
        "ownerName": "张三",
        "ownerPhone": "13800001111",
        "species": "犬",
        "doctor": "李医生",
        "disease": "骨折",
        "status": "待就诊",
        "min": "100.0",
        "max": "5000.0",
        "sortBy": "totalCost",
        "order": "desc",
        "page": "2",
        "pageSize": "15",
    }
    assert result.total == 1
    assert result.page == 1
    assert result.pageSize == 1
    assert result.totalPages == 1
    assert result.totalCost == 100.0
    assert result.items[0].id == "PET-000001"
    assert result.items[0].records is None  # null tolerated
    assert result.items[0].charges is None


@pytest.mark.asyncio
async def test_records_and_charges_arrays_parsed(make_client, pet_factory, list_data_factory, envelope):
    pet = pet_factory(
        records=[{"id": "MR-1", "visitDate": "2024-02-17", "prescription": ["阿莫西林"], "charge": 380.0}],
        charges=[{"id": "CH-1", "item": "血常规", "category": "检查", "amount": 180.0}],
    )

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=envelope(200, "ok", list_data_factory([pet])))

    client = make_client(handler)
    try:
        result = await client.list_pets(ListPetsInput())
    finally:
        await client.aclose()

    assert result.items[0].records[0].prescription == ["阿莫西林"]
    assert result.items[0].charges[0].amount == 180.0


@pytest.mark.asyncio
@pytest.mark.parametrize("status_code", [400, 404, 500, 503])
async def test_backend_4xx_5xx(make_client, status_code):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(status_code, content=json.dumps({"code": status_code, "message": "boom", "time": "t"}).encode())

    client = make_client(handler, retries=0)
    try:
        with pytest.raises(PetHospitalError) as exc:
            await client.list_pets(ListPetsInput())
    finally:
        await client.aclose()

    assert exc.value.envelope.error.code == BACKEND_API_ERROR
    assert exc.value.envelope.error.details["status_code"] == status_code


@pytest.mark.asyncio
async def test_backend_timeout_retries_then_fails(make_client):
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.TimeoutException("timed out", request=request)

    client = make_client(handler, retries=2, timeout=0.2)
    try:
        with pytest.raises(PetHospitalError) as exc:
            await client.list_pets(ListPetsInput())
    finally:
        await client.aclose()

    assert exc.value.envelope.error.code == BACKEND_TIMEOUT
    assert exc.value.envelope.error.details["max_attempts"] == 3  # 2 retries + 1


@pytest.mark.asyncio
async def test_backend_connect_error(make_client):
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("no route", request=request)

    client = make_client(handler, retries=0)
    try:
        with pytest.raises(PetHospitalError) as exc:
            await client.list_pets(ListPetsInput())
    finally:
        await client.aclose()

    assert exc.value.envelope.error.code == BACKEND_UNAVAILABLE


@pytest.mark.asyncio
async def test_backend_invalid_json(make_client):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=b"not-json-at-all", headers={"content-type": "application/json"})

    client = make_client(handler, retries=0)
    try:
        with pytest.raises(PetHospitalError) as exc:
            await client.list_pets(ListPetsInput())
    finally:
        await client.aclose()

    assert exc.value.envelope.error.code == BACKEND_INVALID_RESPONSE


@pytest.mark.asyncio
async def test_backend_envelope_non_success_code(make_client):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=json.dumps({"code": 500, "message": "internal", "time": "t"}).encode())

    client = make_client(handler, retries=0)
    try:
        with pytest.raises(PetHospitalError) as exc:
            await client.list_pets(ListPetsInput())
    finally:
        await client.aclose()

    assert exc.value.envelope.error.code == BACKEND_API_ERROR


@pytest.mark.asyncio
async def test_backend_data_model_mismatch(make_client, envelope):
    def handler(request: httpx.Request) -> httpx.Response:
        # data present but missing required fields (total, page, ...)
        return httpx.Response(200, content=envelope(200, "ok", {"items": "not-a-list"}))

    client = make_client(handler, retries=0)
    try:
        with pytest.raises(PetHospitalError) as exc:
            await client.list_pets(ListPetsInput())
    finally:
        await client.aclose()

    assert exc.value.envelope.error.code == BACKEND_INVALID_RESPONSE
