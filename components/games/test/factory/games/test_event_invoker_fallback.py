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
