"""Blockchain reward learning handler."""

from __future__ import annotations

from typing import Any

from ..learning_contracts import validate_learning_payload
from ..mcp_result import successful_data
from ..models import Event
from ._common import _already_published, _base_payload, _publish, _is_gt_reward


def handle_blockchain_reward(event: Event, invoker: Any) -> dict[str, Any]:
    """Apply blockchain side effects for a computed reward and emit wallet event."""
    payload = event.payload
    amount = float(payload.get("reward_value", 0) or 0)
    if amount <= 0:
        return {"skipped": True, "reason": "zero reward"}

    wallet_id = payload.get("wallet_id") or "wallet-kiro-agent"
    run_ref = payload.get("workflow_run_id") or payload.get("run_id") or ""
    idempotency_key = (
        f"wallet:{run_ref}:"
        f"{payload.get('profile_version', 'v1')}:{amount}"
    )
    # S4b eval-gated payout: non-GT rewards escrow (BOUNTY_ESCROW) at compute
    # time; the wallet credit happens on blockchain_reward_release, fired by
    # the eval projection once durable eval evidence exists for the run.
    # Ground-truth rewards (legacy empty / gt-findings) keep immediate mint.
    if not _is_gt_reward(payload):
        return _escrow_reward_for_run(event, invoker, payload, amount, wallet_id, run_ref)

    if _already_published(invoker, "wallet.rewarded", idempotency_key):
        return {
            **_base_payload(event),
            "status": "committed",
            "reward_value": amount,
            "reward_unit": payload.get("reward_unit", "tokens"),
            "wallet_id": wallet_id,
            "idempotency_key": idempotency_key,
            "deduped": True,
        }

    _ensure_wallet(invoker, wallet_id, payload)

    tx_result = invoker(
        "blockchain_mint",
        to_wallet=wallet_id,
        amount=amount,
        memo=_reward_memo(payload),
    )
    tx = successful_data(tx_result)
    if tx is None or not tx.get("tx_id"):
        return {
            "skipped": True,
            "error": "mint_failed",
        }

    # bd:python-factory-v7imt.1 — Bridge to run_results_store via
    # evals_persist_score so reward events surface in the Evals tab.
    # Defensive: persist failure MUST NOT break the wallet path.
    _bridge_reward_to_evals(invoker, payload, amount)

    derived_payload = {
        **_base_payload(event),
        "status": "committed",
        "reward_value": amount,
        "reward_unit": payload.get("reward_unit", "tokens"),
        "transaction_id": tx.get("tx_id"),
        "wallet_id": wallet_id,
        "idempotency_key": idempotency_key,
    }
    derived_payload = validate_learning_payload("wallet.rewarded", derived_payload)
    _publish(invoker, event, "wallet.rewarded", derived_payload)
    return derived_payload


def _escrow_reward_for_run(
    event: Event, invoker: Any, payload: dict[str, Any],
    amount: float, wallet_id: str, run_ref: str,
) -> dict[str, Any]:
    """Non-GT leg: park the reward as a run-keyed escrow (no immediate credit)."""
    base = _base_payload(event)
    if not run_ref:
        return {"skipped": True, "error": "escrow_requires_run_id"}
    # Same provisioning flow as the GT leg — a missing wallet otherwise drops
    # the payout silently and every redelivery keeps failing.
    _ensure_wallet(invoker, wallet_id, payload)
    result = invoker("blockchain_reward_escrow", run_id=run_ref,
                     to_wallet=wallet_id, amount=amount, memo=_reward_memo(payload))
    escrow = successful_data(result)
    if escrow is None or not escrow.get("tx_id"):
        return {"skipped": True, "error": "escrow_failed"}
    return {
        **base, "status": "escrowed",
        "reward_value": amount, "reward_unit": payload.get("reward_unit", "tokens"),
        "transaction_id": escrow["tx_id"], "wallet_id": wallet_id, "escrowed": True,
    }


def _reward_memo(payload: dict[str, Any]) -> str:
    # bd:python-factory-7ut47 — reward memo prefix uses domain_class with
    # vuln_class fallback so domain-agnostic recipes label their own mints.
    domain = payload.get("domain_class") or payload.get("vuln_class", "")
    return (
        f"RL:{domain}:{payload.get('run_id', '')}:"
        f"F1={float(payload.get('score', 0) or 0):.2f}"
    )


def _ensure_wallet(invoker: Any, wallet_id: str, payload: dict[str, Any]) -> None:
    """Ensure the target wallet exists before mint.

    Mirrors blockchain.runtime.auto_wallet.get_or_create_wallet: probe via
    blockchain_get_wallet (deterministic, returns ``{"error": ...}`` when
    missing), then create with blockchain_create_wallet when absent. Idempotent
    via the existence probe — duplicate create_wallet would raise/error.
    Wallet IDs are deterministic (``wallet-{owner_id}``); the planned
    wallet_id therefore identifies the exact owner principal.
    """
    existing_result = invoker("blockchain_get_wallet", wallet_id=wallet_id)
    existing = successful_data(existing_result)
    if (
        existing is not None
        and existing.get("found", True) is True
        and existing.get("error") is None
    ):
        return
    owner_id = (
        payload.get("principal_id")
        or (wallet_id[len("wallet-"):] if wallet_id.startswith("wallet-") else wallet_id)
    )
    invoker("blockchain_create_wallet", owner_id=owner_id, initial_balance=0)


def _bridge_reward_to_evals(invoker: Any, payload: dict[str, Any], amount: float) -> None:
    """bd:python-factory-v7imt.1 — Bridge reward to evals doc store.

    Uses evals_record_run (the canonical write path) so reward events surface
    in evals_get_dashboard_summary with the correct shape (pass_rate,
    experiment_name, timestamp). Best-effort: wraps, logs, and continues on
    any failure so the wallet path is never interrupted.
    """
    import logging
    _logger = logging.getLogger(__name__)
    try:
        run_id = payload.get("reward_identity") or (
            payload.get("workflow_run_id") or payload.get("run_id", "")
        )
        if not run_id:
            return
        domain_class = payload.get("domain_class") or payload.get("vuln_class", "")
        try:
            score = float(payload.get("score", 0) or 0)
        except (TypeError, ValueError):
            score = 0.0
        score = max(0.0, min(1.0, score))
        target_app = payload.get("target_app", "")
        workflow_type = payload.get("workflow_type", "reward")

        # One reward is one evaluation case: pass_rate is the case outcome,
        # while avg_score retains the continuous reward score.
        case_passed = score >= 0.7
        pass_rate = 1.0 if case_passed else 0.0
        verdict = "PASS" if case_passed else "FAIL"

        invoker(
            "evals_record_run",
            run_id=run_id,
            experiment_name=f"reward:{domain_class}:{target_app}" if domain_class else f"reward:{workflow_type}",
            verdict=verdict,
            pass_rate=round(pass_rate, 3),
            avg_score=round(score, 3),
            total_cases=1,
            passed=1 if verdict == "PASS" else 0,
            failed_cases=0 if verdict == "PASS" else 1,
            case_results=[{
                "case_name": "reward",
                "passed": verdict == "PASS",
                "score": round(score, 3),
            }],
            case_scores=[round(score, 3)],
            summary={
                "total_cases": 1,
                "passed": 1 if verdict == "PASS" else 0,
                "failed_cases": 0 if verdict == "PASS" else 1,
                "pass_rate": round(pass_rate, 3),
                "avg_score": round(score, 3),
            },
            evaluators_used=[],
            agent={},
            source="reward",
        )
    except Exception as exc:
        _logger.warning("v7imt.1 reward->evals bridge failed: %s", exc)
