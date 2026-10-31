"""Eval-gated payout release helper (epic #124 S4b).

Split from _dispatch_evals.py to honor the 200-LOC ratchet. The eval
projection is the payout gate: once durable eval evidence exists for a run,
any reward escrowed under that run_id may be credited — exactly once.
"""
from __future__ import annotations

import logging
from typing import Any

from .mcp_result import successful_data

logger = logging.getLogger(__name__)


def release_eval_gated_reward(invoker: Any, run_id: str) -> None:
    """Credit the reward escrowed for `run_id` (best-effort, once per run).

    Runs after the durable eval_results commit, so eval evidence exists.
    Publishes wallet.rewarded exactly once on the first real wallet movement.
    """
    if not run_id or run_id == "unknown":
        return
    try:
        tx = successful_data(invoker("blockchain_reward_release", run_id=run_id))
        if not tx or not tx.get("tx_id") or not tx.get("to_wallet"):
            return
        idempotency_key = f"wallet:{run_id}:{tx.get('amount', 0)}"
        from .learning_handlers._common import _already_published
        if _already_published(invoker, "wallet.rewarded", idempotency_key):
            return
        payload = {
            "run_id": run_id,
            "workflow_run_id": run_id,
            "status": "committed",
            "reward_value": float(tx.get("amount", 0) or 0),
            "reward_unit": "tokens",
            "transaction_id": tx["tx_id"],
            "wallet_id": str(tx["to_wallet"]),
            "idempotency_key": idempotency_key,
        }
        from .learning_contracts import validate_learning_payload
        payload = validate_learning_payload("wallet.rewarded", payload)
        invoker(
            "events_publish",
            event_type="wallet.rewarded",
            source="events.eval-payout",
            payload=payload,
        )
    except Exception as exc:
        logger.warning("eval-gated reward release failed run_id=%s: %s", run_id, exc)
