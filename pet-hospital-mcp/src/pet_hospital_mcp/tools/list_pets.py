"""`list_pets` MCP tool — wraps `GET /api/v1/pets` from the Go Pet Hospital API.

Input model is strict: unknown fields are rejected, enums use the real backend
values, numeric ranges enforce page >= 1 / 1 <= pageSize <= 500 / min >= 0 /
max >= 0 / min <= max, and NaN/Infinity are rejected. Success output mirrors
the Go `data` envelope: items / total / page / pageSize / totalPages / totalCost.
Errors are returned as a failed tool result carrying the unified error JSON.
"""

from __future__ import annotations

import math
import time
from typing import Any

from pydantic import BaseModel, ConfigDict, ValidationError, field_validator

from pet_hospital_mcp.errors import (
    INTERNAL_ERROR,
    VALIDATION_ERROR,
    PetHospitalError,
    envelope_to_text,
    make_error,
)
from pet_hospital_mcp.logging_config import get_logger

# --- enums: real backend-allowed values (from GET /api/v1/meta) --------------
SPECIES_VALUES = ("犬", "猫", "兔", "鸟", "仓鼠", "爬宠", "其他")
STATUS_VALUES = ("待就诊", "就诊中", "住院中", "已康复", "慢性病随访")
SORT_BY_VALUES = (
    "id",
    "name",
    "ownerName",
    "species",
    "doctor",
    "disease",
    "status",
    "totalCost",
    "visitCount",
    "createdAt",
    "updatedAt",
)
ORDER_VALUES = ("asc", "desc")


# === input ==================================================================
class ListPetsInput(BaseModel):
    """Arguments for `list_pets`.

    Field names mirror the Go API query parameters (camelCase) exactly. Only
    the parameters the Go API accepts are exposed — no adapter-private fields.
    """

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=False)

    q: str | None = None
    name: str | None = None
    ownerName: str | None = None
    ownerPhone: str | None = None
    species: str | None = None
    doctor: str | None = None
    disease: str | None = None
    status: str | None = None
    min: float | None = None
    max: float | None = None
    sortBy: str | None = None
    order: str | None = None
    page: int | None = None
    pageSize: int | None = None

    @field_validator("species")
    @classmethod
    def _check_species(cls, v: str | None) -> str | None:
        if v is not None and v not in SPECIES_VALUES:
            raise ValueError(f"species 必须是 {list(SPECIES_VALUES)} 之一")
        return v

    @field_validator("status")
    @classmethod
    def _check_status(cls, v: str | None) -> str | None:
        if v is not None and v not in STATUS_VALUES:
            raise ValueError(f"status 必须是 {list(STATUS_VALUES)} 之一")
        return v

    @field_validator("sortBy")
    @classmethod
    def _check_sort_by(cls, v: str | None) -> str | None:
        if v is not None and v not in SORT_BY_VALUES:
            raise ValueError(f"sortBy 必须是 {list(SORT_BY_VALUES)} 之一")
        return v

    @field_validator("order")
    @classmethod
    def _check_order(cls, v: str | None) -> str | None:
        if v is not None and v not in ORDER_VALUES:
            raise ValueError(f"order 必须是 {list(ORDER_VALUES)} 之一")
        return v

    @field_validator("min", "max")
    @classmethod
    def _check_finite(cls, v: float | None) -> float | None:
        if v is None:
            return v
        if not math.isfinite(v):
            raise ValueError("min/max 必须是有限数值，不允许 NaN 或 Infinity")
        if v < 0:
            raise ValueError("min/max 必须为非负数")
        return v

    @field_validator("page")
    @classmethod
    def _check_page(cls, v: int | None) -> int | None:
        if v is not None and v < 1:
            raise ValueError("page 必须 >= 1")
        return v

    @field_validator("pageSize")
    @classmethod
    def _check_page_size(cls, v: int | None) -> int | None:
        if v is not None and not (1 <= v <= 500):
            raise ValueError("pageSize 必须在 1..500 之间")
        return v

    def to_query(self) -> dict[str, Any]:
        """Build the query dict sent to the Go API (omitting None)."""
        raw = self.model_dump(exclude_none=True)
        # cross-field: min <= max (only enforced when both present)
        if "min" in raw and "max" in raw and raw["min"] > raw["max"]:
            raise ValueError("min 不能大于 max")
        return raw


# === output (mirrors Go `data`) =============================================
class MedicalRecord(BaseModel):
    model_config = ConfigDict(extra="allow")

    id: str | None = None
    visitDate: str | None = None
    doctor: str | None = None
    diagnosis: str | None = None
    symptoms: str | None = None
    treatment: str | None = None
    prescription: list[str] | None = None
    weightKg: float | None = None
    temperature: float | None = None
    followUp: str | None = None
    charge: float | None = None
    createdAt: str | None = None


class Charge(BaseModel):
    model_config = ConfigDict(extra="allow")

    id: str | None = None
    item: str | None = None
    category: str | None = None
    amount: float | None = None
    doctor: str | None = None
    date: str | None = None


class Pet(BaseModel):
    """A pet record. `records` and `charges` may be null or arrays (Go reality)."""

    model_config = ConfigDict(extra="allow")

    id: str | None = None
    name: str | None = None
    species: str | None = None
    breed: str | None = None
    gender: str | None = None
    ageMonths: int | None = None
    color: str | None = None
    chipNo: str | None = None
    ownerName: str | None = None
    ownerPhone: str | None = None
    ownerAddr: str | None = None
    doctor: str | None = None
    disease: str | None = None
    status: str | None = None
    allergy: str | None = None
    note: str | None = None
    records: list[MedicalRecord] | None = None
    charges: list[Charge] | None = None
    totalCost: float | None = None
    visitCount: int | None = None
    createdAt: str | None = None
    updatedAt: str | None = None


class ListPetsSuccess(BaseModel):
    """Success payload of `list_pets`, matching Go `GET /api/v1/pets` `data`."""

    items: list[Pet]
    total: int
    page: int
    pageSize: int
    totalPages: int
    totalCost: float


# === error output ===========================================================
class ListPetsErrorOutput(BaseModel):
    """Error payload returned when `list_pets` fails (unified error envelope)."""

    error: dict[str, Any]


# === permissive tool argument model =========================================
# The tool's declared input model is intentionally permissive: every field is
# `Any`-typed and unknown fields are ALLOWED. This prevents the SDK from
# rejecting bad input at the protocol layer (which would wrap the raw
# Pydantic/stack text into the result). Strict validation — enums, ranges,
# NaN/Infinity, unknown-field rejection, cross-field min<=max — is performed
# INSIDE the tool body with the strict `ListPetsInput`, so every invalid input
# is reported through the unified {error:{code,message,details}} structure.
class ListPetsArgs(BaseModel):
    """Permissive argument model surfaced as the tool's JSON Schema.

    Kept as a Pydantic model for callers that want a typed argument container
    and for unit-test convenience; the tool function itself declares each
    field as a separate `Any`-typed parameter so the SDK's auto-generated
    schema exposes the 14 Go query parameters as top-level properties (no
    adapter-private `args` wrapper). See the tool description for the real
    allowed values and constraints; they are enforced by `ListPetsInput`
    at call time.
    """

    model_config = ConfigDict(extra="allow")

    q: Any = None
    name: Any = None
    ownerName: Any = None
    ownerPhone: Any = None
    species: Any = None
    doctor: Any = None
    disease: Any = None
    status: Any = None
    min: Any = None
    max: Any = None
    sortBy: Any = None
    order: Any = None
    page: Any = None
    pageSize: Any = None


# Empty but valid `ListPetsSuccess` shape, used as `structured_content` on
# error paths so the SDK's structured-output validation passes (it requires
# the model's mandatory fields to be present in `structured_content`). The
# real error payload travels in `content[0].text` as the unified envelope; the
# `is_error=True` flag tells clients to consult that text, not the structured
# content. (Without this, the SDK raises a ValidationError that gets wrapped as
# "Error executing tool list_pets: ..." — leaking stack text.)
_EMPTY_SUCCESS: dict[str, Any] = {
    "items": [],
    "total": 0,
    "page": 0,
    "pageSize": 0,
    "totalPages": 0,
    "totalCost": 0.0,
}


# === tool registration =======================================================
def register_list_pets(mcp: Any, client: Any) -> None:
    """Register the `list_pets` tool on the given MCPServer, bound to `client`."""

    from mcp.types import CallToolResult, TextContent  # local import: SDK dep

    log = get_logger("list_pets")

    @mcp.tool(
        name="list_pets",
        description=(
            "查询宠物医院档案列表，对应 Go REST API 的 GET /api/v1/pets。\n\n"
            "用途：按关键词、种类、医生、就诊状态、总花费区间等过滤，并支持排序与分页，"
            "返回匹配的宠物档案（含历史病历与消费明细的汇总）。\n\n"
            "参数（均为可选；字段名与 Go 查询参数一致，均为 camelCase）：\n"
            "- q / name / ownerName / ownerPhone：关键词与主人信息\n"
            "- species：种类，可选值 " + "/".join(SPECIES_VALUES) + "\n"
            "- doctor / disease：医生 / 疾病\n"
            "- status：就诊状态，可选值 " + "/".join(STATUS_VALUES) + "\n"
            "- min / max：总花费区间（非负，min<=max，拒绝 NaN/Infinity）\n"
            "- sortBy：排序字段，可选值 " + "/".join(SORT_BY_VALUES) + "\n"
            "- order：排序方向，可选值 asc / desc\n"
            "- page (>=1) / pageSize (1..500)：分页\n"
            "- 未知字段会被拒绝。\n\n"
            "返回：成功时返回 {items,total,page,pageSize,totalPages,totalCost}；"
            "失败时返回统一错误结构 {error:{code,message,details}} 并标记调用失败。"
        ),
        structured_output=True,
    )
    async def list_pets(args: ListPetsArgs) -> ListPetsSuccess:
        from mcp.types import CallToolResult, TextContent  # noqa: F811

        start = time.perf_counter()
        # `ListPetsArgs` is intentionally permissive (every field is `Any`,
        # `extra="allow"`) so the SDK never rejects bad input at the protocol
        # layer — that would wrap raw Pydantic/stack text into the result.
        # Strict validation (enums, ranges, NaN/Infinity, unknown-field
        # rejection, cross-field min<=max) happens here, inside the body,
        # via `ListPetsInput` (which uses `extra="forbid"`), so every invalid
        # input is reported through the unified {error:{code,message,details}}
        # structure with `is_error=True`.
        raw = args.model_dump(exclude_none=True)
        params_dict = dict(raw)
        status_log = "ok"
        try:
            params = ListPetsInput.model_validate(raw)
            params.to_query()  # raises ValueError on min > max
            result = await client.list_pets(params)
            return result
        except PetHospitalError as exc:
            status_log = "error"
            return CallToolResult(
                content=[TextContent(type="text", text=envelope_to_text(exc.envelope))],
                structured_content=dict(_EMPTY_SUCCESS),
                is_error=True,
            )
        except ValidationError as exc:
            status_log = "validation_error"
            return _validation_failed(exc)
        except ValueError as exc:
            # Cross-field (min > max) or other explicit validator message.
            status_log = "validation_error"
            envelope = make_error(
                VALIDATION_ERROR, str(exc), details={"field_errors": []}
            )
            return CallToolResult(
                content=[TextContent(type="text", text=envelope_to_text(envelope))],
                structured_content=dict(_EMPTY_SUCCESS),
                is_error=True,
            )
        except Exception:  # noqa: BLE001 — last resort, never leak stack
            status_log = "internal_error"
            envelope = make_error(
                INTERNAL_ERROR,
                "MCP 适配器内部错误",
                details={},
            )
            return CallToolResult(
                content=[TextContent(type="text", text=envelope_to_text(envelope))],
                structured_content=dict(_EMPTY_SUCCESS),
                is_error=True,
            )
        finally:
            duration_ms = int((time.perf_counter() - start) * 1000)
            log.info(
                "tool_call",
                tool_name="list_pets",
                params=params_dict,
                status=status_log,
                duration_ms=duration_ms,
            )


def _validation_failed(exc: ValidationError) -> Any:
    from mcp.types import CallToolResult, TextContent

    field_errors = []
    for err in exc.errors():
        field_errors.append(
            {"loc": list(err.get("loc", [])), "msg": err.get("msg", "")}
        )
    envelope = make_error(
        VALIDATION_ERROR,
        "工具输入校验失败",
        details={"field_errors": field_errors},
    )
    return CallToolResult(
        content=[TextContent(type="text", text=envelope_to_text(envelope))],
        structured_content=dict(_EMPTY_SUCCESS),
        is_error=True,
    )
