"""Version-2 durable artifacts for paired SDK-native tool chaos runs."""
from __future__ import annotations

from collections import defaultdict
from typing import Any

from .ports import ExperimentReport


def _score(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def build_tool_chaos_artifacts(
    report: ExperimentReport, variant_evidence: list[dict[str, Any]],
) -> dict[str, Any]:
    """Build bounded pair evidence without altering v1 simulation artifacts."""
    pairs: dict[str, dict[str, Any]] = {}
    states: list[dict[str, Any]] = []
    for ordinal, evidence in enumerate(variant_evidence):
        pair_key, condition = evidence["pair_key"], evidence["condition"]
        evidence_key = f"tool-state-{ordinal}"
        states.append({
            "tool_state_evidence_key": evidence_key, "pair_key": pair_key,
            "condition": condition, "tool_states": evidence.get("tool_states", []),
            "effects": evidence.get("effects", {}),
        })
        pair = pairs.setdefault(pair_key, {"pair_key": pair_key, "conditions": {}})
        pair["conditions"][condition] = {"condition": condition, "tool_state_evidence_key": evidence_key}

    scores: dict[tuple[str, str, int], list[float]] = defaultdict(list)
    for ordinal, row in enumerate(report.case_results):
        evidence = row.get("simulation_evidence", {})
        if not isinstance(evidence, dict) or "pair_key" not in evidence:
            continue
        evaluator = row.get("evaluator_ordinal")
        evaluator_key = int(evaluator) if isinstance(evaluator, int) else ordinal
        scores[(evidence["pair_key"], evidence.get("condition", ""), evaluator_key)].append(_score(row.get("score")))

    deltas: list[dict[str, Any]] = []
    for pair_key, pair in pairs.items():
        if "baseline" not in pair["conditions"]:
            continue
        fault_conditions = sorted(condition for condition in pair["conditions"] if condition != "baseline")
        evaluator_keys = {key[2] for key in scores if key[0] == pair_key}
        for condition in fault_conditions:
            for evaluator_key in sorted(evaluator_keys):
                baseline = scores.get((pair_key, "baseline", evaluator_key), [])
                fault = scores.get((pair_key, condition, evaluator_key), [])
                if baseline and fault:
                    base_score = sum(baseline) / len(baseline)
                    fault_score = sum(fault) / len(fault)
                    deltas.append({
                        "pair_key": pair_key, "condition": condition,
                        "evaluator_key": f"evaluator-{evaluator_key}",
                        "baseline_score": base_score, "fault_score": fault_score,
                        "delta": fault_score - base_score,
                    })
        pair["conditions"] = list(pair["conditions"].values())

    return {
        "schema_version": 2, "artifact_kind": "tool_chaos",
        "aggregate": {"overall_score": report.summary.get("overall_score", 0.0), "total_cases": report.summary.get("total_cases", 0)},
        "case_pairs": list(pairs.values()), "tool_state_evidence": states,
        "evaluator_deltas": deltas,
    }
