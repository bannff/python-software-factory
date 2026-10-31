"""Generic scoring dispatch — policy-driven domain-agnostic scoring.

bd:python-factory-v7imt.2. Routes events matched by scoring_policy.yaml
through learning_compute_reward → reward.computed → full learning fan-out
(memory, blockchain, improvement, evals bridge).

RULE: This handler ONLY covers event types that have NO dedicated handler.
Types with dedicated handlers (graph.completed, swarm.completed, chat.*) must
NOT appear in scoring_policy.yaml — see the policy file header for details.

Integration constraints:
  A. Scored results surface in evals dashboard via the v7imt.1 reward->evals
     bridge (reward.py _bridge_reward_to_evals).
  B. Learnings stored with domain_class = source_tag from the policy entry,
     producing a ``{source_tag}-learnings`` recall tag that aligns with
     LearningRecallPlugin's query scheme.
"""
from __future__ import annotations

import fnmatch
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from .models import Event
from .rewards_handler import _emit_reward_event
from .learning_result import normalize_learning_result

logger = logging.getLogger(__name__)

__all__ = ["handle_generic_score_dispatch", "load_scoring_policy", "ScoringPolicyEntry"]

_POLICY_PATH = Path(__file__).parent.parent / "scoring_policy.yaml"


@dataclass(frozen=True, slots=True)
class ScoringPolicyEntry:
    """One row of scoring_policy.yaml.

    Note: evaluator field was removed — learning_compute_reward does not accept
    an evaluator parameter. The engine's registry covenant is "iterate all sources,
    never branch on a caller hint." Source selection is purely self-gating.
    """
    pattern: str
    source_tag: str = ""
    enabled: bool = True


def load_scoring_policy(path: Path | None = None) -> list[ScoringPolicyEntry]:
    """Load and parse scoring_policy.yaml. Returns [] on missing/malformed file."""
    target = path or _POLICY_PATH
    if not target.exists():
        return []
    try:
        data = yaml.safe_load(target.read_text()) or {}
        raw = data.get("policies", [])
        entries = []
        for item in raw:
            if not isinstance(item, dict):
                continue
            entries.append(ScoringPolicyEntry(
                pattern=item.get("pattern", ""),
                source_tag=item.get("source_tag", ""),
                enabled=item.get("enabled", True),
            ))
        return entries
    except Exception as exc:
        logger.warning("scoring_policy: failed to load %s: %s", target, exc)
        return []


def match_policy(event_type: str, policies: list[ScoringPolicyEntry] | None = None) -> ScoringPolicyEntry | None:
    """Find the first enabled policy entry matching the event_type. None = skip."""
    if policies is None:
        policies = load_scoring_policy()
    for entry in policies:
        if not entry.enabled:
            continue
        if fnmatch.fnmatch(event_type, entry.pattern):
            return entry
    return None


def handle_generic_score_dispatch(event: Event, invoker: Any) -> dict[str, Any]:
    """Score an event via the scoring policy. Called from dispatch.py.

    Returns a dict with result or {"skipped": True, "reason": ...}.
    """
    entry = match_policy(event.type)
    if entry is None:
        return {"skipped": True, "reason": f"no policy match for {event.type}"}

    payload = event.payload
    run_id = payload.get("run_id", "")
    if not run_id:
        return {"skipped": True, "reason": "no run_id in payload"}

    # Resolve domain_class: policy source_tag > event's domain_class > event's agent_id
    domain_class = entry.source_tag or payload.get("domain_class") or payload.get("agent_id", "")

    # Inject domain_class into event payload so downstream _build_context picks it up.
    payload["domain_class"] = domain_class

    try:
        kwargs: dict[str, Any] = {
            "run_id": run_id,
            "domain_class": domain_class,
            "workflow_type": payload.get("workflow_type", "auto"),
            "target_app": payload.get("target_app", ""),
        }
        # Forward output/input summaries so llm-judge self-gating can fire.
        if payload.get("input_summary"):
            kwargs["input_summary"] = payload["input_summary"]
        if payload.get("output_summary"):
            kwargs["output_summary"] = payload["output_summary"]
        # Graph/workflow fields.
        graph_id = payload.get("workflow_id") or payload.get("graph_id", "")
        if graph_id:
            kwargs["graph_id"] = graph_id
        vuln_class = payload.get("vuln_class", "")
        if vuln_class:
            kwargs["vuln_class"] = vuln_class

        result = normalize_learning_result(invoker("learning_compute_reward", **kwargs))
    except Exception as exc:
        logger.warning("generic_score_dispatch: compute failed for %s (%s)", event.type, type(exc).__name__)
        return {"skipped": True, "error": "reward_computation_failed"}

    if result is None:
        return {"skipped": True, "error": "reward_computation_failed"}
    if not result.get("source_id"):
        # All sources abstained — no spam.
        return {"skipped": True, "reason": "no reward signal (abstained)"}

    # Canonical top-level fields drive emission; nested raw is evidence only.
    identity = payload.get("reward_identity", "")
    suffix = f"policy:{entry.pattern}{(':' + identity) if identity else ''}"
    reward = _emit_reward_event(invoker, event, result, key_suffix=suffix)

    logger.info(
        "generic_score_dispatch: type=%s run=%s domain=%s source=%s reward=%.1f",
        event.type, run_id, domain_class, result.get("source_id"),
        reward.get("reward_value", 0),
    )
    return {
        "event_type": event.type,
        "run_id": run_id,
        "policy_pattern": entry.pattern,
        "domain_class": domain_class,
        "reward": reward,
    }
