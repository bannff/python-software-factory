"""RL report dict builder — keeps workflow_rl.py under the 200 LOC budget.

Re-exported from ``workflow_rl`` so that test patch paths
``factory.games.runtime.workflow_rl._build_report`` continue to resolve.
"""
from __future__ import annotations

from typing import Any


def build_report(
    *, graph_id: str, run_id: str, vuln_class: str, workflow_type: str,
    target_app: str, findings: list[dict], gt_entries: list[dict],
    scoring: dict[str, Any], blockchain: dict[str, Any], memory: dict[str, Any],
    per_agent: dict[str, int], domain_class: str = "",
) -> dict[str, Any]:
    """Assemble the canonical RL report dict returned by process_workflow_rl.

    Both ``vuln_class`` and ``domain_class`` are emitted (bd:python-factory-twxj0
    + meta-architect Q4 dual-emit verdict) so security and domain consumers can
    each read the field they expect. Values may diverge — e.g.
    ``domain_class="security_idor"`` paired with ``vuln_class="IDOR"``.
    """
    return {
        "graph_id": graph_id, "run_id": run_id,
        "vuln_class": vuln_class,
        "domain_class": domain_class,
        "workflow_type": workflow_type,
        "target_app": target_app,
        "findings_count": len(findings),
        "gt_entries_count": len(gt_entries),
        "scoring": {
            "precision": scoring.get("precision", 0),
            "recall": scoring.get("recall", 0),
            "f1": scoring.get("f1", 0),
            "true_positives": scoring.get("true_positives", 0),
            "false_positives": scoring.get("false_positives_count", 0),
            "false_negatives": scoring.get("false_negatives", 0),
        },
        "blockchain": blockchain, "memory": memory,
        "per_agent": per_agent,
    }
