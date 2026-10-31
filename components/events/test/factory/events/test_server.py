import os

import pytest

from factory.events.server import create_mcp_server


@pytest.mark.skip(reason="Tool events_health_check not yet implemented")
@pytest.mark.asyncio
async def test_health_check(temp_config_dir):
    mcp = create_mcp_server()
    result = await mcp.call_tool("events_health_check", {})

    assert result.structured_content["data"]["status"] == "healthy"


@pytest.mark.skip(reason="Tool events_emit not yet implemented")
@pytest.mark.asyncio
async def test_emit_tool(temp_config_dir):
    mcp = create_mcp_server()
    result = await mcp.call_tool(
        "events_emit",
        {"source": "cli-test", "type": "cli.emit", "payload": {"status": "success"}},
    )

    event_id = result.structured_content["data"]["event_id"]
    assert isinstance(event_id, str)  # UUID

    # Verify via query tool
    query_result = await mcp.call_tool(
        "events_query", {"filter": {"source": "cli-test"}}
    )

    events_data = query_result.structured_content["data"]
    assert len(events_data["events"]) == 1
    assert events_data["events"][0]["payload"]["status"] == "success"


@pytest.mark.skip(reason="Tool events_admin_prune not yet implemented")
@pytest.mark.asyncio
async def test_admin_gate(temp_config_dir):
    # Ensure gate is closed
    os.environ["EVENTS_ENABLE_ADMIN_TOOLS"] = "0"

    from datetime import datetime

    mcp = create_mcp_server()
    result = await mcp.call_tool("events_admin_prune", {"before": datetime.now()})
    assert result.is_error is True
    assert "Admin tools are disabled" in result.content[0].text

    # Open gate
    os.environ["EVENTS_ENABLE_ADMIN_TOOLS"] = "1"
    # Should not raise
    mcp = create_mcp_server()
    result = await mcp.call_tool("events_admin_prune", {"before": datetime.now()})
    assert result.is_error is False
