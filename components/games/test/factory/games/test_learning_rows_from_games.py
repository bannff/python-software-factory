"""A finished game is a learning row on the Games panel (#384)."""
from __future__ import annotations

from factory.games.mcp.learning_progress import build_learning_progress, learning_overview


def _finished(game_id: str, reward: dict, ts: str) -> dict:
    return {
        "event_type": "game.finished", "timestamp": ts, "game_id": game_id,
        "run_id": "", "payload": {
            "game_id": game_id, "game_type": "connect_four", "winner": 1,
            "reward": reward, "move_count": 9,
        },
    }


def test_win_and_loss_become_scored_rows_with_a_trend() -> None:
    rows = build_learning_progress([
        _finished("g1", {"1": -1.0, "2": 1.0}, "2026-11-08T10:00:00Z"),
        _finished("g2", {"1": 1.0, "2": -1.0}, "2026-11-08T11:00:00Z"),
    ])
    by_run = {row["run_id"]: row for row in rows}
    assert set(by_run) == {"game-g1", "game-g2"}
    assert by_run["game-g1"]["f1"] == 0.0 and by_run["game-g2"]["f1"] == 1.0
    assert by_run["game-g2"]["workflow_type"] == "connect_four"
    assert by_run["game-g2"]["trend_direction"] == "improved"
    assert learning_overview(rows)["learning_runs"] == 2


def test_finished_event_without_a_learner_reward_is_ignored() -> None:
    assert build_learning_progress([_finished("g3", {}, "2026-11-08T12:00:00Z")]) == []
