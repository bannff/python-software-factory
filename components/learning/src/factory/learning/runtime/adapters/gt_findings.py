"""Ground-truth findings reward source (built-in).

The first concrete reward source — and the one that preserves today's
behavior byte-for-byte. It delegates scoring to the existing
``games_process_workflow_rl`` tool (findings vs ground-truth P/R/F1) and
maps the result onto a neutral :class:`RewardSignal`:

* ``scalar``       = F1 (0..1)
* ``reward_value`` = planned blockchain amount if present, else F1 * 100
                     (identical to the pre-seam ``rewards_handler`` math)
* ``provenance``   = precision / recall / TP / FP / FN
* ``raw``          = bounded games-source evidence for migration compatibility;
                     canonical reward fields come from the validated signal.

No cross-brick import — it reaches games purely through the MCP invoker
(bd python-factory-pfvo9). It is "gt-findings", one source among many; it
is NOT a domain branch.
"""

from __future__ import annotations

import logging
from math import isfinite
from typing import Any, Callable

from ...core import NO_REWARD, REWARDED
from ..models import RewardSignal
from .mcp_result import successful_data, validate_games_result

logger = logging.getLogger(__name__)

_TOOL = "games_process_workflow_rl"


class GtFindingsRewardSource:
    """Delegates to games_process_workflow_rl and maps to a RewardSignal."""

    source_id = "gt-findings"

    def signal_or_none(
        self, run_ctx: dict[str, Any], invoker: Callable[..., Any] | None,
    ) -> RewardSignal | None:
        """Score via Games; abstain if context, transport, or data is invalid."""
        if invoker is None:
            return None
        # Abstain on runs with no graph to score (e.g. chat turns) — the
        # llm-judge source covers those (bd:pfvo9 slice 2).
        if not run_ctx.get("graph_id"):
            return None
        try:
            rl = successful_data(
                invoker(
                    _TOOL,
                    graph_id=run_ctx.get("graph_id", ""),
                    run_id=run_ctx.get("run_id", ""),
                    vuln_class=run_ctx.get("vuln_class", ""),
                    domain_class=run_ctx.get("domain_class", ""),
                    workflow_type=run_ctx.get("workflow_type", "auto"),
                    target_app=run_ctx.get("target_app", ""),
                ),
                allow_legacy=True,
                validator=validate_games_result,
            )
        except Exception as exc:  # never raise into the engine loop
            logger.warning(
                "gt-findings scoring failed error_type=%s",
                type(exc).__name__,
            )
            return None
        if rl is None:
            return None
        # bd:python-factory-hx5zc — data-driven self-gate (replaces the
        # is_rl_eligible security-skill allowlist domain leak). Abstain only
        # when NO ground truth resolved; a scan WITH ground truth but 0
        # detections is recall=0 (false-negative signal) and MUST score.
        if int(rl.get("gt_entries_count", 0) or 0) <= 0:
            return None
        scoring = rl.get("scoring", {}) if isinstance(rl.get("scoring"), dict) else {}
        scalar = _f1(scoring)
        signal = RewardSignal.from_scalar(
            self.source_id,
            scalar,
            wallet_id=_wallet(rl),
            provenance=_provenance(scoring),
            raw=rl,
        )
        # Preserve the pre-seam reward amount exactly (blockchain.amount wins),
        # and key the verdict off that FINAL amount for byte-identical output.
        signal.reward_value = _amount(rl, scalar)
        signal.verdict = REWARDED if signal.reward_value > 0 else NO_REWARD
        return signal


def _f1(scoring: dict[str, Any]) -> float:
    value = scoring.get("f1", 0)
    if not isinstance(value, (int, float)) or isinstance(value, bool) or not isfinite(float(value)):
        return 0.0
    return max(-1.0, min(1.0, float(value)))


def _amount(rl: dict[str, Any], f1: float) -> float:
    """Mirror legacy amount planning while rejecting malformed values."""
    blockchain = rl.get("blockchain")
    raw_amount = blockchain.get("amount") if isinstance(blockchain, dict) else None
    if isinstance(raw_amount, (int, float)) and not isinstance(raw_amount, bool):
        amount = float(raw_amount)
        if isfinite(amount) and 0 <= amount <= 1_000_000:
            return amount
    return round(max(0.0, f1) * 100, 2)


def _wallet(rl: dict[str, Any]) -> str:
    blockchain = rl.get("blockchain")
    wallet_id = blockchain.get("wallet_id") if isinstance(blockchain, dict) else None
    if isinstance(wallet_id, str) and 1 <= len(wallet_id) <= 128 and all(
        char.isalnum() or char in "_.:-" for char in wallet_id
    ):
        return wallet_id
    return "wallet-kiro-agent"


def _provenance(scoring: dict[str, Any]) -> dict[str, Any]:
    return {
        "precision": scoring.get("precision", 0),
        "recall": scoring.get("recall", 0),
        "true_positives": scoring.get("true_positives", 0),
        "false_positives": scoring.get("false_positives", 0),
        "false_negatives": scoring.get("false_negatives", 0),
    }


__all__ = ["GtFindingsRewardSource"]
