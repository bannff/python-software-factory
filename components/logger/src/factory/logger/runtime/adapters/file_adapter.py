"""File adapter - write logs to local files with query support."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from factory.logger.runtime.ports import LogLevel, LogRecord


class FileSink:
    """Write logs to a local file."""
    
    def __init__(
        self,
        log_dir: str | Path = "./logs",
        filename: str = "factory.log",
        formatter: Any = None,
    ):
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self.log_file = self.log_dir / filename
        self.formatter = formatter
        self._file = None
    
    def _ensure_open(self):
        if self._file is None:
            self._file = open(self.log_file, "a")
    
    def write(self, record: LogRecord) -> None:
        """Write a log record to the file."""
        self._ensure_open()
        if self.formatter:
            line = self.formatter.format(record)
        else:
            # Default: JSON for parseability
            line = json.dumps({
                "timestamp": record.timestamp.isoformat(),
                "level": record.level.value,
                "message": record.message,
                "logger": record.logger_name,
                "source": record.source,
                "run_id": record.run_id,
                "context": record.context,
            }, default=str)
        self._file.write(line + "\n")
    
    def flush(self) -> None:
        if self._file:
            self._file.flush()
    
    def close(self) -> None:
        if self._file:
            self._file.close()
            self._file = None
    
    def health_check(self) -> dict[str, Any]:
        return {
            "sink": "file",
            "log_file": str(self.log_file),
            "log_size": self.log_file.stat().st_size if self.log_file.exists() else 0,
            "exists": self.log_file.exists(),
            "writable": self.log_dir.exists() and self.log_dir.is_dir(),
        }


class FileQuery:
    """Query logs from a local file (assumes JSON format)."""
    
    def __init__(self, log_file: str | Path):
        self.log_file = Path(log_file)
    
    def tail(self, n: int = 20) -> list[LogRecord]:
        """Get the last n log entries."""
        if not self.log_file.exists():
            return []
        
        with open(self.log_file, "r") as f:
            lines = f.readlines()[-n:]
        
        return [self._parse_line(line) for line in lines if line.strip()]
    
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
        if not self.log_file.exists():
            return []
        
        results = []
        with open(self.log_file, "r") as f:
            for line in f:
                if len(results) >= limit:
                    break
                record = self._parse_line(line)
                if record and self._matches(record, level, source, run_id, since, until):
                    results.append(record)
        return results
    
    def _parse_line(self, line: str) -> LogRecord | None:
        """Parse a JSON log line into a LogRecord."""
        try:
            data = json.loads(line.strip())
            return LogRecord(
                level=LogLevel(data.get("level", "info")),
                message=data.get("message", ""),
                timestamp=datetime.fromisoformat(data["timestamp"]),
                logger_name=data.get("logger", "factory"),
                source=data.get("source"),
                run_id=data.get("run_id"),
                context=data.get("context", {}),
            )
        except (json.JSONDecodeError, KeyError, ValueError):
            return None
    
    def _matches(
        self, record: LogRecord, level: LogLevel | None, source: str | None,
        run_id: str | None, since: datetime | None, until: datetime | None,
    ) -> bool:
        if level and record.level != level:
            return False
        if source and record.source != source:
            return False
        if run_id and record.run_id != run_id:
            return False
        if since and record.timestamp < since:
            return False
        if until and record.timestamp > until:
            return False
        return True
