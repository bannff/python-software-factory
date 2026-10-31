"""Backfill legacy run JSON through the canonical immutable Evals writer."""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

_RUNS_DIR = Path(".object_store/eval_runs")


def _request(data: dict[str, Any], run_id: str) -> dict[str, Any]:
    summary = data.get("summary", {})
    return {
        "run_id": run_id, "experiment_name": data.get("experiment_name", ""),
        "timestamp": data.get("timestamp", ""), "verdict": data.get("verdict", "—"),
        "source": data.get("source", "experiment"),
        "pass_rate": float(summary.get("pass_rate", data.get("pass_rate", 0)) or 0),
        "avg_score": float(summary.get("avg_score", data.get("avg_score", 0)) or 0),
        "total_cases": int(summary.get("total_cases", data.get("total_cases", 0)) or 0),
        "passed": int(summary.get("passed", data.get("passed_cases", 0)) or 0),
        "failed_cases": int(summary.get("failed", data.get("failed_cases", 0)) or 0),
        "duration_ms": float(summary.get("duration_ms", data.get("duration_ms", 0)) or 0),
        "evaluators_used": data.get("evaluators_used", []),
        "case_results": data.get("case_results", []), "case_scores": data.get("case_scores", []),
        "agent": data.get("agent", {}), "summary": summary,
    }


def backfill(invoker: Any) -> dict[str, int]:
    """Migrate filesystem artifacts, preserving conflicts rather than overwriting."""
    if not _RUNS_DIR.exists():
        return {"migrated": 0, "already_present": 0, "conflicts": 0, "skipped": 0, "errors": 0, "total_files": 0}
    counts = {"migrated": 0, "already_present": 0, "conflicts": 0, "skipped": 0, "errors": 0}
    files = sorted(_RUNS_DIR.glob("*.json"))
    for path in files:
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            response = invoker("evals_record_run", **_request(data, data.get("run_id", path.stem)))
            from factory.mcp_utils.interface import ToolResult
            envelope = response if isinstance(response, ToolResult) else ToolResult.model_validate(response)
            data = envelope.data.model_dump() if hasattr(envelope.data, "model_dump") else envelope.data
            status = data.get("status", "failed") if envelope.ok and isinstance(data, dict) else "failed"
            if status == "created": counts["migrated"] += 1
            elif status == "matched": counts["already_present"] += 1
            elif status == "conflict": counts["conflicts"] += 1
            else: counts["errors"] += 1
        except json.JSONDecodeError:
            counts["skipped"] += 1
        except Exception as exc:
            counts["errors"] += 1
            print(f"  ERROR {path.name}: {exc}", file=sys.stderr)
    return {**counts, "total_files": len(files)}


if __name__ == "__main__":
    from factory.mcp_utils.interface import get_service
    invoker = get_service("tool_invoker")
    if invoker is None:
        print("ERROR: tool_invoker not available (run inside MCP context)")
        sys.exit(1)
    print(f"Backfill complete: {backfill(invoker)}")
