"""Text formatter - human-readable log output."""

from __future__ import annotations

from factory.logger.runtime.ports import LogRecord


class TextFormatter:
    """Format logs as human-readable text."""
    
    def __init__(self, include_context: bool = True):
        self.include_context = include_context
    
    def format(self, record: LogRecord) -> str:
        """Format a log record as text."""
        ts = record.timestamp.strftime("%Y-%m-%d %H:%M:%S")
        level = record.level.value.upper().ljust(8)
        
        parts = [f"{ts} - {record.logger_name} - {level} - {record.message}"]
        
        # Add source/run_id if present
        meta = []
        if record.source:
            meta.append(f"source={record.source}")
        if record.run_id:
            meta.append(f"run_id={record.run_id}")
        if meta:
            parts.append(f"[{', '.join(meta)}]")
        
        # Add context if enabled and present
        if self.include_context and record.context:
            ctx_str = " ".join(f"{k}={v}" for k, v in record.context.items())
            parts.append(f"| {ctx_str}")
        
        return " ".join(parts)
