"""MCP Prompt registration for Logger brick.

Prompts provide guided workflows for common tasks:
- Debugging errors in logs
- Configuring logging
- Tracing a specific run
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from typing import Any

from .templates import PROMPT_TEMPLATES

if TYPE_CHECKING:
    from factory.logger.runtime.runtime import LoggerRuntime


def register(mcp: Any, runtime: "LoggerRuntime") -> None:
    """Register all Logger prompts with the MCP server."""

    @mcp.prompt()
    def debug_errors(source: str = "") -> str:
        """Generate guidance for debugging errors in logs."""
        # Get recent errors
        errors = runtime.search(level="error", source=source or None, limit=10)
        
        if errors:
            error_lines = []
            for e in errors[:5]:
                error_lines.append(f"- [{e['timestamp']}] {e['message']}")
            error_summary = "\n".join(error_lines)
        else:
            error_summary = "No recent errors found."
        
        return PROMPT_TEMPLATES["debug_errors"]["template"].format(
            error_summary=error_summary,
            source=source or "<brick_name>",
            run_id="<run_id>",
        )

    @mcp.prompt()
    def configure_logging(sink: str = "file") -> str:
        """Generate guidance for configuring logging."""
        health = runtime.health_check()
        current_config = f"Status: {health.get('status', 'unknown')}"
        
        return PROMPT_TEMPLATES["configure_logging"]["template"].format(
            current_config=current_config,
        )

    @mcp.prompt()
    def trace_run(run_id: str) -> str:
        """Generate guidance for tracing all logs for a specific run."""
        entries = runtime.search(run_id=run_id, limit=50)
        
        if entries:
            log_lines = []
            for e in entries:
                log_lines.append(f"[{e['timestamp']}] {e['level'].upper()}: {e['message']}")
            log_entries = "\n".join(log_lines)
            next_steps = "Review the timeline above for anomalies."
        else:
            log_entries = "No logs found for this run_id."
            next_steps = "Verify the run_id is correct, or the run may not have started."
        
        return PROMPT_TEMPLATES["trace_run"]["template"].format(
            run_id=run_id,
            log_entries=log_entries,
            next_steps=next_steps,
        )
