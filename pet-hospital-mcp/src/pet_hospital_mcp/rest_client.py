"""HTTP client wrapping the Go Pet Hospital REST API.

Only `GET /api/v1/pets` is wrapped. Transports httpx exceptions into the
unified `PetHospitalError` shape, with a per-request timeout and a bounded
retry on transient (timeout / connection) failures.
"""

from __future__ import annotations

import httpx

from pet_hospital_mcp.config import Config
from pet_hospital_mcp.errors import (
    BACKEND_API_ERROR,
    BACKEND_INVALID_RESPONSE,
    BACKEND_TIMEOUT,
    BACKEND_UNAVAILABLE,
    PetHospitalError,
)
from pet_hospital_mcp.tools.list_pets import ListPetsInput, ListPetsSuccess


class PetHospitalClient:
    """Thin async client over the Go Pet Hospital REST API."""

    def __init__(
        self,
        base_url: str = "http://127.0.0.1:8080",
        *,
        timeout: float = 5.0,
        retries: int = 2,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout
        self._retries = max(0, retries)
        # A shared client is fine for a stateless service.
        self._client = httpx.AsyncClient(
            base_url=self._base_url,
            timeout=timeout,
            transport=transport,
        )

    @classmethod
    def from_config(cls, config: Config, *, transport: httpx.AsyncBaseTransport | None = None) -> PetHospitalClient:
        return cls(
            base_url=config.base_url,
            timeout=config.backend_timeout,
            retries=config.backend_retries,
            transport=transport,
        )

    async def aclose(self) -> None:
        await self._client.aclose()

    async def list_pets(self, params: ListPetsInput) -> ListPetsSuccess:
        """Call `GET /api/v1/pets` with the given filters and return parsed data."""
        query = params.to_query()
        last_error: PetHospitalError | None = None
        for attempt in range(self._retries + 1):
            try:
                response = await self._client.get("/api/v1/pets", params=query)
                break
            except httpx.TimeoutException as exc:
                last_error = PetHospitalError(
                    BACKEND_TIMEOUT,
                    "上游宠物医院服务请求超时",
                    details={"attempt": attempt + 1, "max_attempts": self._retries + 1},
                )
            except httpx.ConnectError as exc:
                last_error = PetHospitalError(
                    BACKEND_UNAVAILABLE,
                    "无法连接上游宠物医院服务",
                    details={"attempt": attempt + 1, "max_attempts": self._retries + 1},
                )
            except httpx.HTTPError as exc:
                last_error = PetHospitalError(
                    BACKEND_UNAVAILABLE,
                    "与上游宠物医院服务通信失败",
                    details={"attempt": attempt + 1, "error": str(exc)},
                )
        else:
            assert last_error is not None
            raise last_error

        # If the loop broke with a response but a transient error occurred on a
        # prior attempt, last_error is set but ignored — we now process the
        # successful response.

        if response.status_code >= 400:
            raise PetHospitalError(
                BACKEND_API_ERROR,
                "上游宠物医院服务返回错误状态",
                details={
                    "status_code": response.status_code,
                    "body": _safe_text(response.content),
                },
            )

        try:
            payload = response.json()
        except Exception:
            raise PetHospitalError(
                BACKEND_INVALID_RESPONSE,
                "上游返回的内容不是有效的 JSON",
                details={"status_code": response.status_code, "body": _safe_text(response.content)},
            )

        if not isinstance(payload, dict):
            raise PetHospitalError(
                BACKEND_INVALID_RESPONSE,
                "上游返回的响应结构不符合预期",
                details={"status_code": response.status_code},
            )

        code = payload.get("code")
        if code != 200:
            raise PetHospitalError(
                BACKEND_API_ERROR,
                str(payload.get("message") or "上游返回了非成功状态"),
                details={
                    "code": code,
                    "message": payload.get("message"),
                    "time": payload.get("time"),
                },
            )

        data = payload.get("data")
        if not isinstance(data, dict):
            raise PetHospitalError(
                BACKEND_INVALID_RESPONSE,
                "上游响应缺少 data 字段或格式不符",
                details={"status_code": response.status_code},
            )

        try:
            return ListPetsSuccess.model_validate(data)
        except Exception as exc:
            raise PetHospitalError(
                BACKEND_INVALID_RESPONSE,
                "上游响应数据不符合模型定义",
                details={"error": str(exc)},
            )


def _safe_text(content: bytes) -> str:
    try:
        text = content.decode("utf-8", errors="replace")
    except Exception:
        text = "<binary>"
    if len(text) > 500:
        text = text[:500] + "...(truncated)"
    return text
