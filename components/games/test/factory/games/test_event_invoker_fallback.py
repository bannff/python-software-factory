from __future__ import annotations

import sys
import types

from factory.games.runtime import event_emitter


def test_falls_back_to_an_existing_aggregator_without_starting_a_server(monkeypatch) -> None:
    calls = []
    agg = types.SimpleNamespace(invoke_tool=lambda *a, **k: calls.append((a, k)))
    fake = types.SimpleNamespace(get_aggregator=lambda: agg)
    monkeypatch.setitem(sys.modules, "factory.mcp_server.interface", fake)
    monkeypatch.setattr("factory.mcp_utils.interface.get_service", lambda _name: None)
    event_emitter.emit("game.created", {"game_id": "g1"})
    assert calls and calls[0][0][0] == "events_publish" and calls[0][1]["source"] == "games"


def test_no_invoker_is_warned_once_not_silent(monkeypatch, caplog) -> None:
    monkeypatch.setitem(sys.modules, "factory.mcp_server.interface", None)
    monkeypatch.setattr("factory.mcp_utils.interface.get_service", lambda _name: None)
    monkeypatch.setattr(event_emitter, "_warned", False)
    with caplog.at_level("WARNING"):
        event_emitter.emit("game.move", {})
        event_emitter.emit("game.move", {})
    assert len([r for r in caplog.records if "events are dropped" in r.message]) == 1


def test_int_keyed_players_and_rewards_are_published_with_string_keys(monkeypatch) -> None:
    seen = {}
    monkeypatch.setattr("factory.mcp_utils.interface.get_service",
                        lambda _n: (lambda _tool, **kw: seen.update(kw)))
    event_emitter.emit("game.move", {"game_id": "g", "reward": {1: 1.0, 2: -1.0}, "players": {1: "a"}})
    assert seen["payload"]["reward"] == {"1": 1.0, "2": -1.0}
    assert seen["payload"]["players"] == {"1": "a"}


def test_a_rejection_returned_as_a_result_is_logged(monkeypatch, caplog) -> None:
    monkeypatch.setattr("factory.mcp_utils.interface.get_service",
                        lambda _n: (lambda _tool, **kw: {"ok": False, "error": "nope"}))
    with caplog.at_level("WARNING"):
        event_emitter.emit("game.move", {"game_id": "g"})
    assert any("rejected" in r.message and "nope" in r.message for r in caplog.records)
