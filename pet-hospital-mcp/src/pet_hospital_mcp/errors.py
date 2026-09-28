"""Unified structured error format for the Pet Hospital MCP tools.

Wire shape (returned to the MCP client as the tool result text when a call fails):

```json
{"error": {"code": "ERROR_CODE", "message": "可读错误信息", "details": {}}}
```

Error codes:
    VALIDATION_ERROR          — invalid tool input (bad enum/range/type/unknown field)
    BACKEND_TIMEOUT           — upstream Go API timed out
    BACKEND_UNAVAILABLE       — could not connect to the Go API
    BACKEND_API_ERROR         — Go API returned 4xx/5xx or non-success envelope code
    BACKEND_INVALID_RESPONSE — Go API body was not valid JSON or did not match the model
    INTERNAL_ERROR            — unexpected adapter failure
"""

from __future__ import annotations

import re
from typing import Any

from pydantic import BaseModel, Field


# --- error codes -------------------------------------------------------------
VALIDATION_ERROR = "VALIDATION_ERROR"
BACKEND_TIMEOUT = "BACKEND_TIMEOUT"
BACKEND_UNAVAILABLE = "BACKEND_UNAVAILABLE"
BACKEND_API_ERROR = "BACKEND_API_ERROR"
BACKEND_INVALID_RESPONSE = "BACKEND_INVALID_RESPONSE"
INTERNAL_ERROR = "INTERNAL_ERROR"


# --- structured error models -------------------------------------------------
class ErrorDetail(BaseModel):
    code: str
    message: str
    details: dict[str, Any] = Field(default_factory=dict)


class ErrorEnvelope(BaseModel):
    error: ErrorDetail


# --- exception carrying an envelope -----------------------------------------
class PetHospitalError(Exception):
    """Raised by the REST client; converted to a failed tool result by tools."""

    def __init__(self, code: str, message: str, *, details: dict[str, Any] | None = None):
        self.envelope = ErrorEnvelope(
            error=ErrorDetail(code=code, message=message, details=details or {})
        )
        super().__init__(message)


def make_error(
    code: str, message: str, *, details: dict[str, Any] | None = None
) -> ErrorEnvelope:
    return ErrorEnvelope(
        error=ErrorDetail(code=code, message=message, details=details or {})
    )


def envelope_to_text(envelope: ErrorEnvelope) -> str:
    """Serialize an envelope for use as a TextContent payload."""
    import json

    return json.dumps(envelope.model_dump(), ensure_ascii=False)


# --- log desensitization -----------------------------------------------------
# Sensitive keys (case-insensitive) to mask in logs, in both camelCase and
# snake_case forms. Matches substrings so ownerPhone / owner_phone / phone-like
# keys are covered.
_SENSITIVE_PATTERNS = [
    re.compile(r"(?i)^owner_?phone$|^phone$"),
    re.compile(r"(?i)^owner_?addr(ess)?$"),
    re.compile(r"(?i)^chip_?no$"),
]

_MASK = "***"


def _is_sensitive_key(key: str) -> bool:
    for pat in _SENSITIVE_PATTERNS:
        if pat.match(key):
            return True
    return False


def mask_sensitive(value: Any) -> Any:
    """Recursively replace sensitive fields with a mask token.

    Operates on dicts/lists; leaves scalars untouched (used as a structlog
    processor over the event dict). Both camelCase and snake_case keys are
    masked.
    """
    if isinstance(value, dict):
        return {k: (_MASK if _is_sensitive_key(k) else mask_sensitive(v)) for k, v in value.items()}
    if isinstance(value, list):
        return [mask_sensitive(item) for item in value]
    return value
