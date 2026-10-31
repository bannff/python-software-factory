from factory.events.runtime.models import Event
from factory.events.runtime.rewards_handler import handle_rewards_process


def _capture_learning_signal(published):
    return lambda caller: lambda target, **call: (
        published.append((call["arguments"]["event_type"], call["arguments"]["payload"])),
        {"ok": True},
    )[1]


def test_rewards_handler_emits_canonical_learning_events(monkeypatch) -> None:
    published: list[tuple[str, dict]] = []
    monkeypatch.setattr(
        "factory.mcp_utils.interface.get_service",
        lambda name: _capture_learning_signal(published)
        if name == "tool_invoker_for_caller" else None,
    )

    def fake_invoker(tool_name: str, **kwargs):
        if tool_name == "events_query_events":
            return {"events": [], "total": 0}
        if tool_name == "events_publish":
            published.append((kwargs["event_type"], kwargs["payload"]))
            return {"event_id": f"evt-{len(published)}", "status": "published"}
        raise AssertionError(f"unexpected tool: {tool_name}")

    monkeypatch.setattr(
        "factory.events.runtime.rewards_handler._run_rl_loop",
        lambda *args, **kwargs: {
            "source_id": "gt-findings",
            "scoring": {"f1": 0.82, "precision": 0.8, "recall": 0.84},
            "blockchain": {
                "minted": True,
                "amount": 82.0,
                "tx_id": "tx-123",
                "wallet_id": "wallet-kiro-agent",
            },
            "memory": {"stored": True, "memory_id": "mem-123", "content": "summary"},
        },
    )

    event = Event(
        source="agent.graph",
        type="graph.completed",
        payload={
            "run_id": "run-123",
            "graph_id": "rt-scan-idor",
            "workflow_type": "dast",
            "target_app": "WebGoat",
            "execution_time": 1.25,
        },
        principal_id="kiro-agent",
        session_id="sess-1",
        trace_id="req-1",
    )

    result = handle_rewards_process(event, fake_invoker)

    assert result["run_id"] == "run-123"
    event_types = [event_type for event_type, _ in published]
    assert event_types == ["reward.computed"]
    reward_payload = published[0][1]
    assert reward_payload["workflow_run_id"] == "run-123"
    assert reward_payload["score"] == 0.82
    assert reward_payload["reward_value"] == 82.0
    assert reward_payload["duration_ms"] == 1250
    assert reward_payload["precision"] == 0.8
    assert reward_payload["recall"] == 0.84
    assert reward_payload["scalar"] == 0.0


def test_rewards_handler_uses_authoritative_result_fields(monkeypatch) -> None:
    published: list[tuple[str, dict]] = []
    monkeypatch.setattr(
        "factory.mcp_utils.interface.get_service",
        lambda name: _capture_learning_signal(published)
        if name == "tool_invoker_for_caller" else None,
    )

    def invoker(tool_name: str, **kwargs):
        if tool_name == "events_query_events":
            return {"events": [], "total": 0}
        if tool_name == "events_publish":
            published.append((kwargs["event_type"], kwargs["payload"]))
            return {"event_id": "evt-authoritative"}
        raise AssertionError(f"unexpected tool: {tool_name}")

    monkeypatch.setattr(
        "factory.events.runtime.rewards_handler._run_rl_loop",
        lambda *args, **kwargs: {
            "signals": [], "source_id": "custom", "scalar": 0.12,
            "verdict": "penalized", "reward_value": 12.0,
            "wallet_id": "wallet-authoritative", "provenance": {},
            "scoring": {"f1": 0.12},
            "raw": {"blockchain": {"amount": 999999.0, "wallet_id": "attacker"}},
        },
    )
    event = Event(
        source="agent.graph", type="graph.completed",
        payload={"run_id": "run-authoritative", "graph_id": "g"},
    )

    result = handle_rewards_process(event, invoker)
    reward = result["reward"]
    assert reward["reward_value"] == 12.0
    assert reward["wallet_id"] == "wallet-authoritative"
    assert reward["verdict"] == "penalized"
    assert reward["scalar"] == 0.12
    assert published[0][0] == "reward.computed"
    published_reward = published[0][1]
    assert published_reward["reward_value"] == 12.0
    assert published_reward["wallet_id"] == "wallet-authoritative"
    assert published_reward["verdict"] == "penalized"
    assert published_reward["scalar"] == 0.12


def test_rewards_handler_skips_duplicate_reward_event(monkeypatch) -> None:
    published: list[tuple[str, dict]] = []
    monkeypatch.setattr(
        "factory.mcp_utils.interface.get_service",
        lambda name: _capture_learning_signal(published)
        if name == "tool_invoker_for_caller" else None,
    )

    def fake_invoker(tool_name: str, **kwargs):
        if tool_name == "events_query_events":
            return {"events": [{"id": "evt-existing"}], "total": 1}
        if tool_name == "events_publish":
            published.append((kwargs["event_type"], kwargs["payload"]))
            return {"event_id": "evt-new", "status": "published"}
        raise AssertionError(f"unexpected tool: {tool_name}")

    monkeypatch.setattr(
        "factory.events.runtime.rewards_handler._run_rl_loop",
        lambda *args, **kwargs: {
            "source_id": "gt-findings",
            "scoring": {"f1": 0.82, "precision": 0.8, "recall": 0.84},
            "blockchain": {"amount": 82.0, "minted": True},
        },
    )

    event = Event(
        source="agent.graph",
        type="graph.completed",
        payload={"run_id": "run-123", "graph_id": "rt-scan-idor"},
    )

    result = handle_rewards_process(event, fake_invoker)

    assert result["reward"]["deduped"] is True
    assert published == []
