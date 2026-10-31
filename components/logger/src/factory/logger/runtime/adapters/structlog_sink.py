"""Structlog-backed log sink.

Uses `structlog` for structured, context-rich logging with
automatic key-value formatting and processor pipelines.
"""
from __future__ import annotations

from typing import Any

import structlog

from factory.logger.runtime.ports import LogLevel, LogRecord

_LEVEL_MAP = {
    LogLevel.DEBUG: "debug",
    LogLevel.INFO: "info",
    LogLevel.WARNING: "warning",
    LogLevel.ERROR: "error",
    LogLevel.CRITICAL: "critical",
}


class StructlogSink:
    """LogSink implementation backed by structlog.

    Configures structlog with JSON rendering by default.
    Each LogRecord is emitted as a structlog event with
    bound context (source, run_id, tenant_id).
    """

    def __init__(self, *, json_output: bool = True) -> None:
        processors: list[Any] = [
            structlog.stdlib.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
        ]
        if json_output:
            processors.append(structlog.processors.JSONRenderer())
        else:
            processors.append(structlog.dev.ConsoleRenderer())

        structlog.configure(
            processors=processors,
            wrapper_class=structlog.stdlib.BoundLogger,
            context_class=dict,
            logger_factory=structlog.PrintLoggerFactory(),
            cache_logger_on_first_use=True,
        )
        self._logger = structlog.get_logger()

    def write(self, record: LogRecord) -> None:
        bound = self._logger.bind(
            source=record.source,
            run_id=record.run_id,
            tenant_id=record.tenant_id,
            **record.context,
        )
        method = _LEVEL_MAP.get(record.level, "info")
        getattr(bound, method)(record.message)

    def flush(self) -> None:
        pass  # structlog writes immediately

    def close(self) -> None:
        pass  # no resources to release

    def health_check(self) -> dict[str, Any]:
        return {"writable": True, "backend": "structlog"}
