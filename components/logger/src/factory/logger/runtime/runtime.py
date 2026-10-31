"""Logger runtime - the main runtime that coordinates sinks and formatters."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from factory.logger.runtime.ports import LogLevel, LogRecord, LogSink, LogQuery
from factory.logger.runtime.adapters import FileSink, FileQuery, JsonFormatter


class LoggerRuntime:
    """Main logger runtime - coordinates sinks, formatters, and queries."""
    
    def __init__(
        self,
        log_dir: str = "./logs",
        filename: str = "factory.log",
        sink: LogSink | None = None,
        query: LogQuery | None = None,
    ):
        self.log_dir = log_dir
        self.filename = filename
        
        # Use provided sink or default to file with JSON formatter
        if sink:
            self._sink = sink
        else:
            self._sink = FileSink(
                log_dir=log_dir,
                filename=filename,
                formatter=JsonFormatter(),
            )
        
        # Use provided query or default to file query
        if query:
            self._query = query
        else:
            from pathlib import Path
            self._query = FileQuery(Path(log_dir) / filename)
    
    # === Brick Contract ===
    
    def get_capabilities(self) -> dict[str, Any]:
        """Machine-readable feature list."""
        return {
            "name": "logger",
            "version": "1.0.0",
            "features": [
                "structured_logging",
                "log_query",
                "multi_sink",
                "json_format",
                "text_format",
            ],
            "sinks": ["file"],  # Could add: cloudwatch, datadog, otel
            "formatters": ["json", "text"],
        }
    
    def health_check(self) -> dict[str, Any]:
        """Fast readiness probe."""
        sink_health = self._sink.health_check()
        return {
            "status": "healthy" if sink_health.get("writable", False) else "degraded",
            "sink": sink_health,
        }
    
    def describe_config_schema(self) -> dict[str, Any]:
        """JSON schema for configuration."""
        return {
            "type": "object",
            "properties": {
                "log_dir": {"type": "string", "default": "./logs"},
                "filename": {"type": "string", "default": "factory.log"},
                "format": {"type": "string", "enum": ["json", "text"], "default": "json"},
                "level": {
                    "type": "string",
                    "enum": ["debug", "info", "warning", "error", "critical"],
                    "default": "info",
                },
            },
        }
    
    # === Logging Operations ===
    
    def log(
        self,
        level: str | LogLevel,
        message: str,
        *,
        source: str | None = None,
        run_id: str | None = None,
        tenant_id: str | None = None,
        context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Log a message at the specified level."""
        if isinstance(level, str):
            level = LogLevel(level.lower())
        
        record = LogRecord(
            level=level,
            message=message,
            timestamp=datetime.now(timezone.utc),
            source=source,
            run_id=run_id,
            tenant_id=tenant_id,
            context=context or {},
        )
        
        self._sink.write(record)
        self._sink.flush()
        
        return {
            "status": "logged",
            "level": level.value,
            "timestamp": record.timestamp.isoformat(),
        }
    
    def info(self, message: str, **kwargs) -> dict[str, Any]:
        return self.log(LogLevel.INFO, message, **kwargs)
    
    def error(self, message: str, **kwargs) -> dict[str, Any]:
        return self.log(LogLevel.ERROR, message, **kwargs)
    
    def warning(self, message: str, **kwargs) -> dict[str, Any]:
        return self.log(LogLevel.WARNING, message, **kwargs)
    
    def debug(self, message: str, **kwargs) -> dict[str, Any]:
        return self.log(LogLevel.DEBUG, message, **kwargs)
    
    # === Query Operations ===
    
    def tail(self, n: int = 20) -> list[dict[str, Any]]:
        """Get the last n log entries."""
        records = self._query.tail(n=n)
        return [self._record_to_dict(r) for r in records]
    
    def search(
        self,
        *,
        level: str | None = None,
        source: str | None = None,
        run_id: str | None = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        """Search logs with filters."""
        log_level = LogLevel(level.lower()) if level else None
        records = self._query.search(
            level=log_level, source=source, run_id=run_id, limit=limit
        )
        return [self._record_to_dict(r) for r in records]
    
    def _record_to_dict(self, record: LogRecord) -> dict[str, Any]:
        return {
            "timestamp": record.timestamp.isoformat(),
            "level": record.level.value,
            "message": record.message,
            "source": record.source,
            "run_id": record.run_id,
            "context": record.context,
        }
    
    # === Admin Operations ===
    
    def clear(self) -> dict[str, Any]:
        """Clear the log file (admin operation)."""
        from pathlib import Path
        log_file = Path(self.log_dir) / self.filename
        if log_file.exists():
            with open(log_file, "w") as f:
                f.write("")
        return {"status": "cleared", "file": str(log_file)}
    
    def close(self) -> None:
        """Close the logger and release resources."""
        self._sink.close()
