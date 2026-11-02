"""Events subscription authoring updates the active Hook registry."""
from __future__ import annotations
import pytest

@pytest.mark.asyncio
async def test_subscription_upsert_and_delete_update_live_registry(tmp_path, monkeypatch) -> None:
    from factory.events.server import create_tool_catalog
    monkeypatch.setenv("EVENTS_CONFIG_DIR", str(tmp_path))
    monkeypatch.setenv("EVENTS_ENABLE_AUTHORING_TOOLS", "1")
    catalog = create_tool_catalog()
    data = {"id": "review-hook", "event_type": "review.*", "handler": "review.handle",
            "description": "Review events", "filters": {}, "enabled": False, "priority": 2}
    saved = await catalog.call_tool("events_authoring_upsert_subscription", {
        "subscription_id": "review-hook", "subscription_data": data, "dry_run": False,
    })
    assert saved.structured_content["data"]["ok"] is True
    listed = await catalog.call_tool("events_get_subscription_registry", {})
    hook = next(row for row in listed.structured_content["data"]["subscriptions"]
                if row["id"] == "review-hook")
    assert hook == {
        "id": "review-hook", "event_type": "review.*", "handler": "review.handle",
        "description": "Review events", "enabled": False, "priority": 2, "has_filters": False,
        "origin": "authored",
    }
    data["enabled"] = True
    await catalog.call_tool("events_authoring_upsert_subscription", {
        "subscription_id": "review-hook", "subscription_data": data, "dry_run": False,
    })
    listed = await catalog.call_tool("events_get_subscription_registry", {})
    assert listed.structured_content["data"]["subscriptions"][0]["enabled"] is True
    await catalog.call_tool("events_authoring_delete_subscription", {"subscription_id": "review-hook"})
    listed = await catalog.call_tool("events_get_subscription_registry", {})
    assert "review-hook" not in {
        row["id"] for row in listed.structured_content["data"]["subscriptions"]
    }


@pytest.mark.asyncio
async def test_set_enabled_keeps_priority_and_filters_and_system_rows_are_read_only(tmp_path, monkeypatch) -> None:
    from factory.events.server import create_tool_catalog
    monkeypatch.setenv("EVENTS_CONFIG_DIR", str(tmp_path))
    monkeypatch.setenv("EVENTS_ENABLE_AUTHORING_TOOLS", "1")
    catalog = create_tool_catalog()
    data = {"id": "keep-me", "event_type": "a.*", "handler": "h", "description": "d",
            "filters": {"kind": "x"}, "enabled": True, "priority": 42}
    await catalog.call_tool("events_authoring_upsert_subscription", {
        "subscription_id": "keep-me", "subscription_data": data, "dry_run": False})
    toggled = await catalog.call_tool("events_authoring_set_enabled", {
        "subscription_id": "keep-me", "enabled": False})
    assert toggled.structured_content["data"]["ok"] is True
    rows = (await catalog.call_tool("events_get_subscription_registry", {})).structured_content["data"]["subscriptions"]
    row = next(r for r in rows if r["id"] == "keep-me")
    assert (row["enabled"], row["priority"], row["has_filters"], row["origin"]) == (False, 42, True, "authored")
    stored = (tmp_path / "subscriptions" / "keep-me.yaml").read_text()
    assert "priority: 42" in stored and "kind: x" in stored
    system = [r for r in rows if r["origin"] == "system"]
    assert system, "shipped subscriptions must be reported as system"
    refused = await catalog.call_tool("events_authoring_set_enabled", {
        "subscription_id": system[0]["id"], "enabled": False})
    assert refused.structured_content["data"]["ok"] is False
