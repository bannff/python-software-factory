"""Structured confidence classification — 5-level system.

Deterministic classification using formal rules. No LLM needed.
Operates on structural signals (consensus, taint trace, mitigating
controls) not vuln-specific patterns — polymorphic across all
vuln classes.

Levels:
  Strong_Safe      — mitigating controls confirmed, low risk
  Medium_Safe      — likely safe but incomplete evidence
  Weak_Suspicious  — suspicious but no proof
  Likely_Vulnerable — strong evidence, needs confirmation
  Confirmed        — high confidence, multiple signals agree
"""
from __future__ import annotations

from typing import Any


LEVELS = [
    "Strong_Safe", "Medium_Safe", "Weak_Suspicious",
    "Likely_Vulnerable", "Confirmed",
]

# Rules encoded as (condition_fn, level) — first match wins
_RULES: list[tuple[str, Any]] = []  # populated by classify()


def classify(
    agent_consensus: int = 1,
    total_agents: int = 3,
    has_taint_trace: bool = False,
    has_mitigating_control: bool = False,
    has_code_evidence: bool = False,
    is_sensitive_operation: bool = False,
    historical_tp_rate: float | None = None,
    confidence_score: float = 0.5,
) -> dict[str, Any]:
    """Classify confidence using formal rules.

    Args:
        agent_consensus: How many agents agreed on this finding.
        total_agents: Total agents in the ensemble.
        has_taint_trace: Whether a concrete taint path exists.
        has_mitigating_control: Whether mitigating controls found.
        has_code_evidence: Whether code snippet is grounded.
        is_sensitive_operation: Payment, role change, delete, etc.
        historical_tp_rate: TP rate from prior scans (0-1, or None).
        confidence_score: Raw confidence from agent (0-1).
    """
    consensus_ratio = agent_consensus / max(total_agents, 1)

    # Rule 1: Mitigating control confirmed → Strong_Safe
    if has_mitigating_control and not is_sensitive_operation:
        return _result("Strong_Safe", 0.1, "Mitigating control confirmed")

    # Rule 2: Mitigating control on sensitive op → Medium_Safe
    # (controls exist but sensitive ops need extra scrutiny)
    if has_mitigating_control and is_sensitive_operation:
        return _result("Medium_Safe", 0.3, "Control exists but sensitive operation")

    # Rule 3: No code evidence → Weak_Suspicious (hallucination risk)
    if not has_code_evidence:
        return _result("Weak_Suspicious", 0.4, "No grounded code evidence")

    # Rule 4: Single agent, no taint trace → Weak_Suspicious
    if consensus_ratio < 0.5 and not has_taint_trace:
        return _result("Weak_Suspicious", 0.45, "Low consensus, no taint trace")

    # Rule 5: Majority consensus + taint trace → Confirmed
    if consensus_ratio >= (2 / 3) and has_taint_trace:
        level = "Confirmed"
        score = min(0.95, confidence_score + 0.1)
        return _result(level, score, "Majority consensus with taint trace")

    # Rule 6: Majority consensus, no taint → Likely_Vulnerable
    if consensus_ratio >= (2 / 3):
        return _result("Likely_Vulnerable", confidence_score, "Majority consensus")

    # Rule 7: Taint trace but low consensus → Likely_Vulnerable
    if has_taint_trace and consensus_ratio >= 0.33:
        return _result("Likely_Vulnerable", confidence_score, "Taint trace with partial consensus")

    # Rule 8: Historical TP rate boost
    if historical_tp_rate is not None and historical_tp_rate > 0.7:
        return _result("Likely_Vulnerable", confidence_score,
                        f"Historical TP rate {historical_tp_rate:.0%}")

    # Rule 9: Sensitive operation boost
    if is_sensitive_operation and confidence_score >= 0.6:
        return _result("Likely_Vulnerable", confidence_score, "Sensitive operation")

    # Default: Weak_Suspicious
    return _result("Weak_Suspicious", confidence_score, "Insufficient evidence")


def _result(level: str, score: float, reason: str) -> dict[str, Any]:
    return {
        "confidence_level": level,
        "confidence_score": round(min(1.0, max(0.0, score)), 3),
        "reason": reason,
        "level_index": LEVELS.index(level),
    }
