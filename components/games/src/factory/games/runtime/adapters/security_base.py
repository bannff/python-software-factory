"""Shared base for all security game adapters.

Implements GameRules protocol for single-player vulnerability finding.
Subclasses override game_type and optionally _validate_finding.
Ground truth in config["ground_truth"]: {"vulnerabilities": [...], "false_positives": [...]}
Scoring: 4-axis (correctness, evidence, completeness, efficiency).
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from ..ports import GameState, MoveResult
from ...core import STATUS_ACTIVE, STATUS_FINISHED

SECURITY_PLAYER = 1
DEFAULT_MAX_ACTIONS = 20
VALID_ACTIONS = (
    "analyze_code", "trace_dataflow", "submit_finding",
    "check_config", "test_endpoint", "read_file",
)
_LEGAL_MOVES = [{"action": a, "description": f"Perform {a.replace('_', ' ')}"} for a in VALID_ACTIONS]


class SecurityGameRules:
    """Base for all security-focused game adapters."""

    game_type: str = "security_base"

    def create_initial_state(
        self, game_id: str, config: dict[str, Any] | None = None,
    ) -> GameState:
        cfg = config or {}
        now = datetime.now(timezone.utc).isoformat()
        gt = cfg.get("ground_truth", {"vulnerabilities": [], "false_positives": []})
        return GameState(
            game_id=game_id, game_type=self.game_type, board=[[0]],
            current_player=SECURITY_PLAYER, status=STATUS_ACTIVE,
            players={SECURITY_PLAYER: "agent"},
            config={"ground_truth": gt,
                    "max_actions": cfg.get("max_actions", DEFAULT_MAX_ACTIONS),
                    "difficulty": cfg.get("difficulty", "medium"),
                    "found_vuln_ids": []},
            created_at=now, updated_at=now,
        )

    def legal_moves(self, state: GameState) -> list[dict[str, Any]]:
        if state.status != STATUS_ACTIVE:
            return []
        if len(state.move_history) >= state.config.get("max_actions", DEFAULT_MAX_ACTIONS):
            return []
        return list(_LEGAL_MOVES)

    def apply_move(
        self, state: GameState, player: int, move: dict[str, Any],
    ) -> MoveResult:
        if state.status != STATUS_ACTIVE:
            return MoveResult(valid=False, error="Game is not active")
        if player != SECURITY_PLAYER:
            return MoveResult(valid=False, error="Security games are single-player")
        action = move.get("action")
        if action not in VALID_ACTIONS:
            return MoveResult(
                valid=False,
                error=f"Invalid action: {action}. Must be one of {VALID_ACTIONS}",
            )
        now = datetime.now(timezone.utc).isoformat()
        state.move_history.append({"action": action, "move": move, "ts": now})
        state.updated_at = now

        if action == "submit_finding":
            return self._score_finding(state, move)
        # Non-submission: record and check exhaustion
        if len(state.move_history) >= state.config.get("max_actions", DEFAULT_MAX_ACTIONS):
            return self._exhaust_actions(state)
        return MoveResult(valid=True, state=state, reward={SECURITY_PLAYER: 0.0},
                          terminal=False, info={"action": action})

    def evaluate(self, state: GameState) -> dict[str, Any]:
        gt = state.config.get("ground_truth", {})
        vulns = gt.get("vulnerabilities", [])
        found = state.config.get("found_vuln_ids", [])
        max_act = state.config.get("max_actions", DEFAULT_MAX_ACTIONS)
        used = len(state.move_history)
        total = len(vulns) or 1
        completeness = len(found) / total
        efficiency = max(0.0, 1.0 - (used / max_act)) if max_act else 0.0
        clamp = lambda v: min(1.0, max(0.0, v))  # noqa: E731
        return {
            "correctness": clamp(self._calc_correctness(state)),
            "evidence": clamp(self._calc_evidence(state)),
            "completeness": clamp(completeness),
            "efficiency": clamp(efficiency),
            "vulns_found": len(found), "vulns_total": len(vulns),
            "actions_used": used,
        }

    # -- Scoring helpers (overridable) ------------------------------------

    def _score_finding(self, state: GameState, move: dict[str, Any]) -> MoveResult:
        gt = state.config.get("ground_truth", {})
        vulns = gt.get("vulnerabilities", [])
        fps = gt.get("false_positives", [])
        finding_id = move.get("finding_id", "")

        if finding_id in fps:
            return self._make_result(state, -0.5, info={"match": "false_positive"})

        reward, match_info = self._match_vulnerability(
            vulns, move.get("type", ""), move.get("location", ""),
            state.config.get("found_vuln_ids", []),
        )
        if match_info.get("matched_id"):
            found = state.config.get("found_vuln_ids", [])
            if match_info["matched_id"] not in found:
                found.append(match_info["matched_id"])
                state.config["found_vuln_ids"] = found

        all_found = vulns and len(state.config.get("found_vuln_ids", [])) >= len(vulns)
        if all_found:
            state.status = STATUS_FINISHED
            return MoveResult(valid=True, state=state, reward={SECURITY_PLAYER: reward},
                              terminal=True, info={**match_info, "all_found": True})
        return self._make_result(state, reward, info=match_info)

    def _match_vulnerability(
        self, vulns: list[dict], finding_type: str,
        finding_loc: str, already_found: list[str],
    ) -> tuple[float, dict[str, Any]]:
        for v in vulns:
            if v.get("id") in already_found:
                continue
            if v.get("type") == finding_type:
                loc_score = self._location_similarity(v.get("location", ""), finding_loc)
                if loc_score >= 0.5:
                    return 0.5 + 0.5 * loc_score, {
                        "match": "vulnerability", "matched_id": v["id"], "loc_score": loc_score}
        return -0.1, {"match": "none"}

    @staticmethod
    def _location_similarity(expected: str, actual: str) -> float:
        if not expected or not actual:
            return 0.0
        exp_file, act_file = expected.split(":")[0], actual.split(":")[0]
        if exp_file != act_file:
            return 0.0
        if ":" in expected and ":" in actual and expected.split(":")[1] == actual.split(":")[1]:
            return 1.0
        return 0.5

    def _validate_finding(self, move: dict[str, Any]) -> bool:
        """Override in subclasses for type-specific evidence checks."""
        return True

    # -- Internal helpers -------------------------------------------------

    def _make_result(
        self, state: GameState, reward: float, *, info: dict[str, Any] | None = None,
    ) -> MoveResult:
        max_act = state.config.get("max_actions", DEFAULT_MAX_ACTIONS)
        if len(state.move_history) >= max_act:
            state.status = STATUS_FINISHED
            return MoveResult(valid=True, state=state, reward={SECURITY_PLAYER: reward},
                              terminal=True, info={**(info or {}), "exhausted": True})
        return MoveResult(valid=True, state=state, reward={SECURITY_PLAYER: reward},
                          terminal=False, info=info or {})

    @staticmethod
    def _exhaust_actions(state: GameState) -> MoveResult:
        state.status = STATUS_FINISHED
        return MoveResult(valid=True, state=state, reward={SECURITY_PLAYER: -1.0},
                          terminal=True, info={"exhausted": True})

    def _calc_correctness(self, state: GameState) -> float:
        subs = [m for m in state.move_history if m.get("action") == "submit_finding"]
        if not subs:
            return 0.0
        return sum(1 for s in subs if s.get("move", {}).get("type")) / len(subs)

    def _calc_evidence(self, state: GameState) -> float:
        subs = [m for m in state.move_history if m.get("action") == "submit_finding"]
        if not subs:
            return 0.0
        return sum(1 for s in subs if s.get("move", {}).get("evidence")) / len(subs)
