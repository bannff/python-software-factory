"""RL planning helpers: reward/learning payloads + per-agent summary.

Re-exported from ``workflow_rl`` so test patch paths
(`factory.games.runtime.workflow_rl._plan_reward`, `_plan_learning`,
`_per_agent_summary`) continue to resolve.
"""
from __future__ import annotations

from typing import Any


def _plan_reward(scoring: dict[str, Any]) -> dict[str, Any]:
    """Describe the reward outcome that downstream events should materialize."""
    try:
        f1 = float(scoring.get("f1", 0) or 0)
    except Exception:
        f1 = 0.0
    if f1 <= 0:
        return {
            "eligible": False,
            "amount": 0.0,
            "wallet_id": "wallet-kiro-agent",
            "status": "no_reward",
            "reason": "zero F1",
        }
    return {
        "eligible": True,
        "amount": round(f1 * 100, 2),
        "wallet_id": "wallet-kiro-agent",
        "status": "pending_event",
    }


def _plan_learning(
    scoring: dict[str, Any], run_id: str,
    vuln_class: str, wtype: str, target_app: str,
    domain_class: str = "",
) -> dict[str, Any]:
    """Describe the learning summary that downstream events should persist.

    ``domain_class`` (bd:python-factory-twxj0) coalesces with ``vuln_class``
    so the memory tag prefix matches whichever is set; security recipes can
    keep passing ``vuln_class`` while domain agents pass ``domain_class``.
    Pattern matches ``game_pipeline.py`` per meta-architect Q4 verdict.
    """
    domain = domain_class or vuln_class
    return {
        "stored": False,
        "status": "pending_event",
        "summary_type": "workflow_rl",
        "domain": domain,
        "content": (
            f"RL [{wtype}] {domain} {target_app} run={run_id}: "
            f"F1={scoring.get('f1', 0):.2f} "
            f"P={scoring.get('precision', 0):.2f} "
            f"R={scoring.get('recall', 0):.2f} "
            f"TP={scoring.get('true_positives', 0)} "
            f"FP={scoring.get('false_positives_count', 0)} "
            f"FN={scoring.get('false_negatives', 0)}"
        ),
    }


def _per_agent_summary(findings: list[dict]) -> dict[str, int]:
    """Count findings per agent_id."""
    counts: dict[str, int] = {}
    for f in findings:
        aid = f.get("agent_id", "unknown")
        counts[aid] = counts.get(aid, 0) + 1
    return counts
