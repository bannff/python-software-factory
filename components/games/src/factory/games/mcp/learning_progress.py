"""RL learning-progression aggregation for the Games dashboard.

The Games runtime emits lifecycle events for every workflow run. This module
turns that event stream into compact, per-run learning rows so the declared UI
can answer whether an agent is improving without a bespoke frontend surface.
"""
from __future__ import annotations

from collections import defaultdict
from typing import Any


_PHASE_LABELS = {
    "rl.started": "Started",
    "rl.findings.collected": "Findings collected",
    "rl.scored": "Scored",
    "rl.reward.processed": "Reward processed",
    "rl.memory.processed": "Learning stored",
    "rl.completed": "Completed",
    "rl.failed": "Failed",
}


def build_learning_progress(activities: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Return newest-first learning rows derived from RL lifecycle events."""
    events_by_run: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for activity in activities:
        if not str(activity.get("event_type", "")).startswith("rl."):
            continue
        run_id = str(activity.get("run_id", ""))
        if run_id:
            events_by_run[run_id].append(activity)

    rows = [_learning_row(run_id, events) for run_id, events in events_by_run.items()]
    rows.sort(key=lambda item: str(item.get("timestamp", "")), reverse=True)
    _add_trends(rows)
    return rows


def learning_overview(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Compute the small summary values shown above the learning list."""
    scores = [float(row["f1"]) for row in rows if row.get("f1") is not None]
    return {
        "learning_runs": len(rows),
        "best_f1": max(scores, default=0.0),
        "cumulative_reward": round(sum(float(row["reward"]) for row in rows), 3),
        "learning_stored": sum(row.get("learning_state") == "stored" for row in rows),
    }


def _learning_row(run_id: str, events: list[dict[str, Any]]) -> dict[str, Any]:
    ordered = sorted(events, key=lambda item: str(item.get("timestamp", "")))
    latest = ordered[-1]
    scored = _latest_event(ordered, "rl.scored") or _latest_event(ordered, "rl.completed")
    reward = _latest_event(ordered, "rl.reward.processed")
    memory = _latest_event(ordered, "rl.memory.processed")
    event_types = {str(item.get("event_type", "")) for item in ordered}
    f1 = _number(scored, "f1") if scored else None
    return {
        "run_id": run_id,
        "workflow_type": latest.get("workflow_type", "workflow"),
        "target_app": latest.get("target_app", ""),
        "domain": latest.get("domain_class") or latest.get("vuln_class", ""),
        "graph_id": latest.get("graph_id", ""),
        "timestamp": latest.get("timestamp", ""),
        "age_label": latest.get("age_label", ""),
        "status": _status(event_types),
        "learning_state": _outcome(memory, default="pending"),
        "f1": f1,
        "precision": _number(scored, "precision") if scored else None,
        "recall": _number(scored, "recall") if scored else None,
        "true_positives": _number(scored, "true_positives", integer=True) if scored else None,
        "false_positives": _number(scored, "false_positives", integer=True) if scored else None,
        "false_negatives": _number(scored, "false_negatives", integer=True) if scored else None,
        "reward": _number(reward, "amount") if reward else 0.0,
        "reward_state": _outcome(reward, default="pending"),
        "recent_f1": [
            _number(item, "f1") for item in ordered
            if item.get("event_type") in {"rl.scored", "rl.completed"}
            and _number(item, "f1") is not None
        ],
        "phases": [
            {"phase": _PHASE_LABELS.get(str(item.get("event_type")), item.get("label", "")),
             "outcome": item.get("outcome", "completed"),
             "timestamp": item.get("timestamp", "")}
            for item in ordered
        ],
    }


def _add_trends(rows: list[dict[str, Any]]) -> None:
    """Attach cross-run score histories and directions for renderer-dumb convergence."""
    previous: float | None = None
    history: list[float] = []
    for row in reversed(rows):
        score = row.get("f1")
        if score is None:
            row["trend_direction"] = "baseline"
            row["f1_delta"] = 0.0
            row["score_history"] = list(history)
            continue
        current = float(score)
        history.append(current)
        row["score_history"] = list(history)
        if previous is None:
            row["trend_direction"] = "baseline"
            row["f1_delta"] = 0.0
        else:
            delta = current - previous
            row["f1_delta"] = round(delta * 100, 1)
            row["trend_direction"] = (
                "improved" if delta > 0.001 else "regressed" if delta < -0.001 else "steady"
            )
        previous = current


def _latest_event(events: list[dict[str, Any]], event_type: str) -> dict[str, Any] | None:
    return next((item for item in reversed(events) if item.get("event_type") == event_type), None)


def _status(event_types: set[str]) -> str:
    if "rl.failed" in event_types:
        return "failed"
    if "rl.completed" in event_types:
        return "completed"
    return "active"


def _outcome(event: dict[str, Any] | None, *, default: str) -> str:
    return str(event.get("outcome", default)) if event else default


def _number(event: dict[str, Any] | None, key: str, *, integer: bool = False) -> float | int | None:
    if event is None or event.get(key) is None:
        return None
    try:
        value = float(event[key])
        return int(value) if integer else value
    except (TypeError, ValueError):
        return None
