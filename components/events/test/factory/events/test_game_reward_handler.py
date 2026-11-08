"""game.finished → learning reward fan-out (#384). Real learning runtime behind the handler."""
from __future__ import annotations

from factory.events.runtime.game_reward_handler import handle_game_reward
from factory.events.runtime.models import Event
from factory.learning.runtime.adapters.game_outcome import GameOutcomeRewardSource
from factory.learning.runtime.registry import RewardSourceRegistry
from factory.learning.runtime.runtime import LearningRuntime
from factory.mcp_utils.interface import ToolResult, set_service


def _invoker(published: list):
    set_service("tool_invoker_for_caller", lambda caller: lambda target, **call: (
        published.append((call["arguments"]["event_type"], call["arguments"]["payload"])),
        {"ok": True},
    )[1])
    reg = RewardSourceRegistry()
    reg.register_builtin(GameOutcomeRewardSource())
    runtime = LearningRuntime(reg)

    def _invoke(tool: str, **kw):
        if tool == "events_query_events":
            return {"events": [], "total": 0}
        if tool == "learning_compute_reward":
            ctx = {"run_id": kw.get("run_id", ""), "domain_class": kw.get("domain_class", ""),
                   "workflow_type": kw.get("workflow_type", ""), "game_reward": kw.get("game_reward")}
            return ToolResult(ok=True, data=runtime.compute(ctx, None)).model_dump(mode="json")
        if tool == "events_publish":
            published.append((kw["event_type"], kw["payload"]))
            return {"event_id": "evt", "status": "published"}
        raise AssertionError(f"unexpected tool: {tool}")

    return _invoke


def _finished(reward=None, game_id="g1"):
    payload = {"game_id": game_id, "game_type": "connect_four", "winner": 1,
               "reward": {"1": 1.0, "2": -1.0} if reward is None else reward, "move_count": 9}
    return Event(source="games", type="game.finished", payload=payload, principal_id="kiro-agent")


def test_win_emits_one_reward_keyed_by_game_id() -> None:
    published: list = []
    result = handle_game_reward(_finished(), _invoker(published))
    reward = result["reward"]
    assert reward["source_id"] == "game-outcome" and reward["run_id"] == "game-g1"
    assert reward["domain_class"] == "connect_four"
    assert reward["idempotency_key"] == "reward:game-g1:v1:game"


def test_loss_is_penalized() -> None:
    result = handle_game_reward(_finished({"1": -1.0, "2": 1.0}), _invoker([]))
    assert result["reward"]["verdict"] == "penalized"
    assert result["reward"]["reward_value"] == 0.0


def test_event_without_reward_or_id_is_skipped() -> None:
    assert handle_game_reward(_finished({}), _invoker([]))["skipped"] is True
    ev = Event(source="games", type="game.finished", payload={"reward": {"1": 1.0}})
    assert handle_game_reward(ev, _invoker([]))["skipped"] is True
