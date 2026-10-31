"""JSON formatter - agent-friendly structured log output."""

from __future__ import annotations

import json
from typing import Any

from factory.logger.runtime.ports import LogRecord


class JsonFormatter:
    """Format logs as JSON - ideal for agent parsing and log aggregation."""
    
    def __init__(self, pretty: bool = False):
        self.pretty = pretty
    
    def format(self, record: LogRecord) -> str:
        """Format a log record as JSON."""
        data: dict[str, Any] = {
            "timestamp": record.timestamp.isoformat(),
            "level": record.level.value,
            "message": record.message,
            "logger": record.logger_name,
        }
        
        # Add optional fields if present
        if record.source:
            data["source"] = record.source
        if record.run_id:
            data["run_id"] = record.run_id
        if record.tenant_id:
            data["tenant_id"] = record.tenant_id
        if record.context:
            data["context"] = record.context
        
        if self.pretty:
            return json.dumps(data, indent=2, default=str)
        return json.dumps(data, default=str)
