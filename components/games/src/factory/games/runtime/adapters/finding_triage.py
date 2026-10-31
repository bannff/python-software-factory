"""Finding Triage game adapter (classification game).

Agent classifies security findings as TP/FP/needs-info.
Unlike other security games, the agent doesn't find vulns —
it triages pre-existing findings against ground truth labels.

submit_finding takes {"finding_id": "...", "classification": "tp|fp|needs_info"}
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from ..ports import GameState, MoveResult
from ...core import STATUS_ACTIVE, STATUS_FINISHED
from .security_base import SecurityGameRules, SECURITY_PLAYER, DEFAULT_MAX_ACTIONS

TRIAGE_ACTIONS = (
    "analyze_code", "trace_dataflow", "submit_finding",
    "check_config", "read_file",
)
VALID_CLASSIFICATIONS = ("tp", "fp", "needs_info")


class FindingTriageRules(SecurityGameRules):
    """Finding triage game — classify findings as TP/FP/needs-info."""

    game_type: str = "finding_triage"

    def create_initial_state(
        self, game_id: str, config: dict[str, Any] | None = None,
    ) -> GameState:
        state = super().create_initial_state(game_id, config)
        gt = state.config.get("ground_truth", {})
        # Ensure findings_to_triage exists in config
        state.config["findings_to_triage"] = gt.get("findings_to_triage", [])
        state.config["triaged_ids"] = []
        return state

    def _score_finding(self, state: GameState, move: dict[str, Any]) -> MoveResult:
        """Score a triage classification against ground truth labels."""
        finding_id = move.get("finding_id", "")
        classification = move.get("classification", "")
        findings = state.config.get("findings_to_triage", [])
        triaged = state.config.get("triaged_ids", [])

        if classification not in VALID_CLASSIFICATIONS:
            return self._make_result(state, -0.1, info={
                "error": f"Invalid classification: {classification}"})

        # Find the ground truth label for this finding
        gt_label = None
        for f in findings:
            if f.get("id") == finding_id:
                gt_label = f.get("label")
                break

        if gt_label is None:
            return self._make_result(state, -0.1, info={"match": "unknown_finding"})

        # Score: correct classification = +1.0, wrong = -0.3
        correct = classification == gt_label
        reward = 1.0 if correct else -0.3

        if finding_id not in triaged:
            triaged.append(finding_id)
            state.config["triaged_ids"] = triaged

        # Check if all findings triaged
        all_triaged = len(triaged) >= len(findings) and findings
        if all_triaged:
            state.status = STATUS_FINISHED
            return MoveResult(
                valid=True, state=state, reward={SECURITY_PLAYER: reward},
                terminal=True, info={"correct": correct, "all_triaged": True},
            )
        return self._make_result(state, reward, info={"correct": correct})
