"""Tests for payments MCP server.

Tests the server module directly without mocking FastMCP,
using the real create_mcp_server() factory function.
"""

import asyncio

from factory.payments.server import create_mcp_server, get_capabilities, create_payment_intent


def _get_tool(server, name: str):
    """Get a tool by name from the MCP server."""
    return asyncio.run(server.get_tool(name))


class TestMCPServer:
    """Tests for payments MCP server contract."""

    def test_capabilities(self) -> None:
        caps = get_capabilities()
        assert caps["version"] == "1.0.0"
        assert "USD" in caps["currencies_supported"]

    def test_create_payment_intent(self) -> None:
        result = create_payment_intent(amount=10.00, currency="USD", customer_id="cust_123")
        assert result["status"] == "succeeded"
        assert result["amount"]["amount"] == "10.00"

    def test_create_payment_intent_decline_mock(self) -> None:
        result = create_payment_intent(amount=10.99, currency="USD")
        assert result["status"] == "failed"
        assert "decline" in result["error_message"]

    def test_server_has_contract_tools(self) -> None:
        """Verify the server exposes required contract tools."""
        server = create_mcp_server()
        tool_names = [t.name for t in asyncio.run(server.list_tools())]
        assert "payments_get_capabilities" in tool_names
        assert "payments_health_check" in tool_names
        assert "payments_describe_config_schema" in tool_names
