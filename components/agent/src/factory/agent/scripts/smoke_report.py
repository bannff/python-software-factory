"""Report generation for smoke tests."""
from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

logger = logging.getLogger("smoke_test")

REPORT_DIR = Path("projects/companion_x/challenges/experiments")


def extract_tool_calls(result: Any) -> list[dict]:
    """Extract tool call info from AgentResult.metrics."""
    calls = []
    try:
        metrics = getattr(result, "metrics", None)
        if metrics is None:
            return calls
        tool_metrics = getattr(metrics, "tool_metrics", {})
        for name, tm in tool_metrics.items():
            tool_info = getattr(tm, "tool", {}) or {}
            calls.append({
                "tool": name,
                "call_count": getattr(tm, "call_count", 0),
                "success_count": getattr(tm, "success_count", 0),
                "error_count": getattr(tm, "error_count", 0),
                "input_keys": list(
                    (tool_info.get("input") or {}).keys()
                ),
            })
    except Exception as e:
        logger.warning("Could not extract tool calls: %s", e)
    return calls


def build_report(
    run_id: str, config_name: str, node_id: str,
    model: str, elapsed: float, error: str | None,
    tool_calls: list[dict], result: Any,
) -> dict:
    """Build a smoke test report dict."""
    tool_names = {c["tool"] for c in tool_calls}
    total_calls = sum(c.get("call_count", 1) for c in tool_calls)
    # Extract token usage from metrics
    usage = {}
    try:
        metrics = getattr(result, "metrics", None)
        if metrics:
            usage = getattr(metrics, "accumulated_usage", {}) or {}
    except Exception:
        pass
    return {
        "run_id": run_id,
        "config": config_name,
        "node_id": node_id,
        "model": model,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "elapsed_seconds": round(elapsed, 1),
        "status": "error" if error else "completed",
        "error": error,
        "tool_calls_count": total_calls,
        "tool_calls": tool_calls[:20],
        "unique_tools": sorted(tool_names),
        "token_usage": dict(usage) if usage else {},
        "checks": {
            "called_file_read": "file_read" in tool_names,
            "called_think": "think" in tool_names,
            "called_memory": any("memory" in t for t in tool_names),
            "called_graph": any("graph" in t for t in tool_names),
            "called_security": any(
                "security" in t or "classify" in t
                for t in tool_names
            ),
        },
        "output_preview": str(result)[:500] if result else None,
    }


def write_report(report: dict) -> Path:
    """Write report JSON and return path."""
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    path = REPORT_DIR / f"{report['run_id']}.json"
    path.write_text(json.dumps(report, indent=2))
    logger.info("Report: %s", path)
    logger.info(
        "Tools: %s | Checks: %s",
        report["unique_tools"],
        {k: v for k, v in report["checks"].items() if v},
    )
    return path
