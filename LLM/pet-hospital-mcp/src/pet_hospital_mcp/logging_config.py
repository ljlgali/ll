"""Structured JSON logging via structlog.

Every tool call is logged with:
    timestamp, tool_name, params, status, duration_ms

Sensitive fields (ownerPhone/ownerAddr/chipNo, plus snake_case forms) are
masked recursively before serialization.
"""

from __future__ import annotations

import logging
from typing import Any

import structlog

from pet_hospital_mcp.errors import mask_sensitive


def _desensitize_processor(
    logger: Any, method_name: str, event_dict: dict[str, Any]
) -> dict[str, Any]:
    """Mask sensitive values anywhere in the event dict (recursively)."""
    for key, value in list(event_dict.items()):
        event_dict[key] = mask_sensitive(value)
    return event_dict


def configure_logging(level: str = "INFO") -> None:
    """Idempotent structlog + stdlib configuration."""
    logging.basicConfig(
        format="%(message)s",
        stream=None,
    )
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso", utc=True, key="timestamp"),
            _desensitize_processor,
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(
            getattr(logging, level.upper(), logging.INFO)
        ),
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )


def get_logger(name: str | None = None) -> structlog.stdlib.BoundLogger:
    return structlog.get_logger(name)
