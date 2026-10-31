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
