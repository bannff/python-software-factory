"""File-backed store for eval run results.

Persists results to .object_store/eval_runs/{run_id}.json using atomic
writes. Mirrors the sop_store.py pattern.
"""
from __future__ import annotations

import json
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_RUNS_DIR = Path(".object_store/eval_runs")


def _ensure_dir() -> None:
    _RUNS_DIR.mkdir(parents=True, exist_ok=True)


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


def save_run(
    experiment_name: str,
    case_results: list[dict[str, Any]],
    summary: dict[str, Any],
    evaluators_used: list[str],
    model_id: str,
    system_prompt: str,
    duration_ms: float = 0.0,
    source: str = "experiment",
) -> str:
    """Persist a run result. Returns the run_id."""
    _ensure_dir()
    run_id = uuid.uuid4().hex[:12]
    ts = _utcnow()
    passes = [r for r in case_results if r.get("passed")]
    verdict = "PASS" if case_results and len(passes) == len(case_results) else "FAIL"
    scores = [r.get("score", 0.0) for r in case_results]
    avg_score = sum(scores) / len(scores) if scores else 0.0
    pass_rate = len(passes) / len(case_results) if case_results else 0.0

    enriched_cases = []
    for r in case_results:
        inp = r.get("input", r.get("case_name", ""))
        out = r.get("output", r.get("actual", ""))
        enriched_cases.append({
            "case_name": r.get("case_name", ""),
            "input_snippet": str(inp)[:120] if inp else "",
            "output_snippet": str(out)[:120] if out else "",
            "score": r.get("score", 0.0),
            "passed": r.get("passed", False),
            "reason": r.get("reason", ""),
            "evaluator": r.get("evaluator", evaluators_used[0] if evaluators_used else ""),
        })

    data = {
        "run_id": run_id,
        "experiment_name": experiment_name,
        "timestamp": ts,
        "verdict": verdict,
        "source": source,
        "agent": {
            "model_id": model_id,
            "system_prompt_snippet": system_prompt[:80],
        },
        "evaluators_used": evaluators_used,
        "summary": {
            **summary,
            "pass_rate": round(pass_rate, 3),
            "avg_score": round(avg_score, 3),
            "total_cases": len(case_results),
            "passed": len(passes),
            "failed": len(case_results) - len(passes),
            "duration_ms": round(duration_ms, 1),
        },
        "case_results": enriched_cases,
        "case_scores": scores,
    }

    path = _RUNS_DIR / f"{run_id}.json"
    tmp = _RUNS_DIR / f"{run_id}.json.tmp"
    tmp.write_text(json.dumps(data, indent=2), encoding="utf-8")
    os.replace(tmp, path)
    return run_id


def list_runs() -> list[dict[str, Any]]:
    """List all persisted runs, newest first."""
    if not _RUNS_DIR.exists():
        return []
    runs_asc = []
    for f in sorted(_RUNS_DIR.glob("*.json"), key=lambda p: p.stat().st_mtime):
        try:
            d = json.loads(f.read_text(encoding="utf-8"))
            summary = d.get("summary", {})
            runs_asc.append({
                "run_id": d.get("run_id", f.stem),
                "experiment_name": d.get("experiment_name", ""),
                "timestamp": d.get("timestamp", ""),
                "verdict": d.get("verdict", "—"),
                "source": d.get("source", "experiment"),
                "pass_rate": summary.get("pass_rate", 0.0),
                "avg_score": summary.get("avg_score", 0.0),
                "total_cases": summary.get("total_cases", 0),
                "passed_cases": summary.get("passed", 0),
                "failed_cases": summary.get("failed", 0),
                "duration_ms": summary.get("duration_ms", 0.0),
                "evaluators_used": d.get("evaluators_used", []),
                "case_scores": d.get("case_scores", []),
                "agent": d.get("agent", {}),
            })
        except (json.JSONDecodeError, OSError):
            continue

    previous_by_experiment: dict[str, dict[str, Any]] = {}
    for run in runs_asc:
        previous = previous_by_experiment.get(run["experiment_name"])
        pass_rate_delta = 0.0
        avg_score_delta = 0.0
        trend_direction = "flat"
        regression_state = "baseline"

        if previous is not None:
            pass_rate_delta = round(run["pass_rate"] - previous["pass_rate"], 3)
            avg_score_delta = round(run["avg_score"] - previous["avg_score"], 3)
            if pass_rate_delta > 0.01:
                trend_direction = "up"
                regression_state = "improved"
            elif pass_rate_delta < -0.01:
                trend_direction = "down"
                regression_state = "regressed"
            else:
                regression_state = "steady"

            if run["verdict"] == "FAIL" and previous["verdict"] == "PASS":
                regression_state = "regressed"
                trend_direction = "down"
            elif run["verdict"] == "PASS" and previous["verdict"] == "FAIL":
                regression_state = "improved"
                trend_direction = "up"

        run["previous_run_id"] = previous.get("run_id") if previous else None
        run["pass_rate_delta"] = pass_rate_delta
        run["avg_score_delta"] = avg_score_delta
        run["trend_direction"] = trend_direction
        run["regression_state"] = regression_state
        previous_by_experiment[run["experiment_name"]] = run

    return list(reversed(runs_asc))


def get_run(run_id: str) -> dict[str, Any] | None:
    """Load a full run result by ID."""
    path = _RUNS_DIR / f"{run_id}.json"
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return None
