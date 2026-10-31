"""Abstract ports for logger brick.

Ports define what capabilities the logger needs, not how they're implemented.
Adapters plug in specific frameworks (structlog, loguru, CloudWatch, etc.)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Protocol


class LogLevel(Enum):
    """Standard log levels."""
    DEBUG = "debug"
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


@dataclass
class LogRecord:
    """A single log entry - framework-agnostic representation."""
    level: LogLevel
    message: str
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    logger_name: str = "factory"
    context: dict[str, Any] = field(default_factory=dict)
    
    # Optional metadata
    source: str | None = None  # e.g., "agent", "workflow", "auth"
    run_id: str | None = None  # correlation ID for tracing
    tenant_id: str | None = None  # multi-tenant support


class LogSink(Protocol):
    """Port: Where logs are written (file, stdout, CloudWatch, etc.)"""
    
    def write(self, record: LogRecord) -> None:
        """Write a log record to the sink."""
        ...
    
    def flush(self) -> None:
        """Flush any buffered logs."""
        ...
    
    def close(self) -> None:
        """Close the sink and release resources."""
        ...
    
    def health_check(self) -> dict[str, Any]:
        """Check sink health/status."""
        ...


class LogFormatter(Protocol):
    """Port: How logs are formatted (JSON, text, colored, etc.)"""
    
    def format(self, record: LogRecord) -> str:
        """Format a log record as a string."""
        ...


class LogQuery(Protocol):
    """Port: Query/search logs (optional capability)."""
    
    def tail(self, n: int = 20) -> list[LogRecord]:
        """Get the last n log entries."""
        ...
    
    def search(
        self,
        *,
        level: LogLevel | None = None,
        source: str | None = None,
        run_id: str | None = None,
        since: datetime | None = None,
        until: datetime | None = None,
        limit: int = 100,
    ) -> list[LogRecord]:
        """Search logs with filters."""
        ...
