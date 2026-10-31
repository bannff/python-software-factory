"""Compute neutral rewards and emit the canonical reward.computed event."""
from __future__ import annotations

import logging
from math import isfinite
from numbers import Real
from typing import Any

from .learning_contracts import validate_learning_payload
from .learning_handlers._common import _already_published, publish_learning_signal
from .learning_result import normalize_learning_result
from .models import Event

logger = logging.getLogger(__name__)
_MAX_REWARD_VALUE = 1_000_000.0
_DEFAULT_WALLET = "wallet-kiro-agent"


def handle_rewards_process(event: Event, invoker: Any) -> dict[str, Any]:
    """Compute and emit a reward for a completed graph/swarm event."""
    payload = event.payload
    run_id = payload.get("run_id", "")
    graph_id = payload.get("workflow_id") or payload.get("graph_id", "")
    vuln_class = payload.get("vuln_class", "")
    domain_class = payload.get("domain_class") or vuln_class
    if not run_id:
        return {"skipped": True, "reason": "no run_id in payload"}
    rl_result = _run_rl_loop(
        invoker, graph_id, run_id, vuln_class,
        payload.get("workflow_type", "auto"), payload.get("target_app", ""),
        domain_class,
    )
    if rl_result.get("error"):
        return {"skipped": True, "reason": "reward computation failed"}
    if not rl_result.get("source_id"):
        return {"skipped": True, "reason": "no reward signal (abstained)"}
    reward_event = _emit_reward_event(invoker, event, rl_result)
    logger.info(
        "rewards: run=%s F1=%.2f reward=%.1f",
        run_id, _number(_mapping(rl_result.get("scoring")).get("f1")),
        reward_event.get("reward_value", 0),
    )
    return {"run_id": run_id, "graph_id": graph_id, "rl": rl_result, "reward": reward_event}


def _run_rl_loop(
    invoker: Any, graph_id: str, run_id: str, vuln_class: str,
    workflow_type: str, target_app: str, domain_class: str = "",
) -> dict[str, Any]:
    """Call Learning and retain its authoritative top-level result fields."""
    try:
        result = normalize_learning_result(invoker(
            "learning_compute_reward", graph_id=graph_id, run_id=run_id,
            vuln_class=vuln_class, domain_class=domain_class,
            workflow_type=workflow_type, target_app=target_app,
        ))
    except Exception as exc:
        logger.warning("rewards: reward computation failed (%s)", type(exc).__name__)
        return {"error": "reward_computation_failed"}
    return result or {"error": "reward_computation_failed"}


def _emit_reward_event(
    invoker: Any, event: Event, rl_result: dict[str, Any], key_suffix: str = "",
) -> dict[str, Any]:
    """Emit reward.computed using canonical fields; raw remains evidence only."""
    context = _build_context(event)
    scoring = _mapping(rl_result.get("scoring"))
    amount = _reward_amount(rl_result, scoring)
    reward_payload = {
        **context,
        "status": "completed" if not rl_result.get("error") else "failed",
        "score": _number(scoring.get("f1")),
        "scalar": _number(rl_result.get("scalar")),
        "precision": _number(scoring.get("precision")),
        "recall": _number(scoring.get("recall")),
        "true_positives": _integer(scoring.get("true_positives")),
        "false_positives": _integer(scoring.get("false_positives")),
        "false_negatives": _integer(scoring.get("false_negatives")),
        "reward_value": amount,
        "reward_unit": "tokens",
        "wallet_id": _reward_wallet(rl_result),
        "verdict": _verdict(rl_result, amount),
        "source_id": rl_result.get("source_id", ""),
        "provenance": rl_result.get("provenance", {}) or {},
        "duration_ms": _duration_ms(event.payload),
        "idempotency_key": f"reward:{context['workflow_run_id']}:{context['profile_version']}"
        f"{(':' + key_suffix) if key_suffix else ''}",
    }
    if _already_published(invoker, "reward.computed", reward_payload["idempotency_key"]):
        return {**reward_payload, "deduped": True}
    publish_learning_signal(
        invoker, event, "reward.computed",
        validate_learning_payload("reward.computed", reward_payload),
    )
    return reward_payload


def _reward_amount(rl_result: dict[str, Any], scoring: dict[str, Any]) -> float:
    """Use canonical reward_value; only bounded legacy top-level data can fall back."""
    if "reward_value" in rl_result:
        return _bounded_number(rl_result.get("reward_value"))
    blockchain = rl_result.get("blockchain")
    if isinstance(blockchain, dict) and "amount" in blockchain:
        return _bounded_number(blockchain.get("amount"))
    return round(_bounded_number(scoring.get("f1")) * 100, 2)


def _reward_wallet(rl_result: dict[str, Any]) -> str:
    """Use canonical wallet_id; never authorize a wallet from raw evidence."""
    if "wallet_id" in rl_result:
        return _safe_wallet(rl_result.get("wallet_id"))
    blockchain = rl_result.get("blockchain")
    return _safe_wallet(blockchain.get("wallet_id")) if isinstance(blockchain, dict) else _DEFAULT_WALLET


def _verdict(rl_result: dict[str, Any], amount: float) -> str:
    value = rl_result.get("verdict")
    return value if value in {"rewarded", "no_reward", "penalized"} else (
        "rewarded" if amount > 0 else "no_reward"
    )


def _build_context(event: Event) -> dict[str, Any]:
    payload = event.payload
    workflow_id = payload.get("workflow_id") or payload.get("graph_id", "")
    return {
        "run_id": payload.get("run_id", ""),
        "workflow_run_id": payload.get("workflow_run_id", payload.get("run_id", "")),
        "workflow_id": workflow_id, "graph_id": workflow_id,
        "session_id": event.session_id or payload.get("session_id", ""),
        "tenant_id": payload.get("tenant_id", ""),
        "principal_id": event.principal_id or payload.get("principal_id", ""),
        "profile_id": payload.get("profile_id", "default"),
        "profile_version": payload.get("profile_version", "v1"),
        "target_app": payload.get("target_app", ""),
        "workflow_type": payload.get("workflow_type", "auto"),
        "vuln_class": payload.get("vuln_class", ""),
        "domain_class": payload.get("domain_class") or payload.get("vuln_class", ""),
        "reward_identity": payload.get("reward_identity", ""),
    }


def _mapping(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _number(value: Any, default: float = 0.0) -> float:
    return float(value) if isinstance(value, Real) and not isinstance(value, bool) and isfinite(float(value)) else default


def _bounded_number(value: Any) -> float:
    number = _number(value)
    return number if 0 <= number <= _MAX_REWARD_VALUE else 0.0


def _integer(value: Any) -> int:
    return int(value) if isinstance(value, int) and not isinstance(value, bool) else 0


def _safe_wallet(value: Any) -> str:
    if isinstance(value, str) and 1 <= len(value) <= 128 and all(
        char.isalnum() or char in "_.:-" for char in value
    ):
        return value
    return _DEFAULT_WALLET


def _duration_ms(payload: dict[str, Any]) -> int:
    return int(_number(payload.get("execution_time")) * 1000)


__all__ = ["_emit_reward_event", "handle_rewards_process"]
