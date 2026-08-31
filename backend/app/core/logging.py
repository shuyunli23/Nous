"""Structured logging setup.

Console renderer in development, JSON lines in production (``LOG_JSON=true``).
A ``request_id`` context variable is bound to every log record so a single HTTP
request can be traced across services and background tasks.
"""

from __future__ import annotations

import logging
import sys
from contextvars import ContextVar
from typing import Any

import structlog

from app.core.config import settings

request_id_ctx: ContextVar[str | None] = ContextVar("request_id", default=None)

_configured = False


def _add_request_id(
    _logger: Any, _name: str, event_dict: dict[str, Any]
) -> dict[str, Any]:
    request_id = request_id_ctx.get()
    if request_id:
        event_dict.setdefault("request_id", request_id)
    return event_dict


def configure_logging() -> None:
    """Configure structlog + stdlib logging. Idempotent."""
    global _configured
    if _configured:
        return

    level = getattr(logging, settings.log_level, logging.INFO)

    shared_processors: list[Any] = [
        structlog.contextvars.merge_contextvars,
        _add_request_id,
        structlog.stdlib.add_log_level,
        structlog.processors.TimeStamper(fmt="iso", utc=True),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
    ]

    renderer: Any = (
        structlog.processors.JSONRenderer()
        if settings.log_json
        else structlog.dev.ConsoleRenderer(colors=False)
    )

    structlog.configure(
        processors=[*shared_processors, renderer],
        wrapper_class=structlog.make_filtering_bound_logger(level),
        logger_factory=structlog.PrintLoggerFactory(file=sys.stdout),
        cache_logger_on_first_use=True,
    )

    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=level,
        force=True,
    )
    # uvicorn already formats access logs; keep them but quiet the noisy ones.
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("chromadb").setLevel(logging.WARNING)

    _configured = True


def get_logger(name: str | None = None) -> structlog.stdlib.BoundLogger:
    """Return a structlog logger with ``logger=<module>`` already bound."""
    configure_logging()
    logger = structlog.get_logger()
    if name:
        logger = logger.bind(logger=name)
    return logger
