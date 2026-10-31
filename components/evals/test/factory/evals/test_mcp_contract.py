"""Tests for evals MCP contract tools.

Every MCP-enabled brick MUST expose:
- get_capabilities() - Machine-readable feature list
- health_check() - Fast readiness probe
- describe_config_schema() - JSON schema for configuration
"""

from __future__ import annotations

import asyncio

import pytest

from factory.evals.server import get_mcp_server
from factory.evals.runtime.runtime import reset_runtime


def _get_tool(name: str):
    """Get a tool by name from the MCP server."""
    mcp = get_mcp_server()
    return asyncio.run(mcp.get_tool(name))


@pytest.fixture(autouse=True)
def reset_state():
    """Reset runtime state between tests."""
    reset_runtime()
    yield
    reset_runtime()


class TestScoreGt:
    """The MCP boundary must preserve explicit matcher selections."""

    def test_empty_match_on_is_not_replaced_by_default(self) -> None:
        tool = _get_tool("evals_score_gt")
        result = tool.fn(
            findings=[{"cwe": "CWE-639", "method": "GET", "path": "/users/{id}"}],
            gt_entries=[{
                "cwe": "CWE-639",
                "artifact": {"method": "GET", "path": "/users/{id}"},
            }],
            match_on=[],
        )
        assert result.ok
        assert result.data.true_positives == 0
        assert result.data.false_positives_count == 1
        assert result.data.false_negatives == 0

    def test_score_evidence_is_bounded_without_changing_counts(self) -> None:
        tool = _get_tool("evals_score_gt")
        findings = [{"cwe": f"CWE-{index}"} for index in range(300)]
        result = tool.fn(findings=findings, gt_entries=findings, match_on=["cwe"])
        assert result.ok
        assert result.data.true_positives == 300
        assert len(result.data.matched) == 256

class TestGetCapabilities:
    """Tests for get_capabilities contract tool."""

    def test_tool_registered(self) -> None:
        """get_capabilities tool must be registered."""
        tool = _get_tool("get_capabilities")
        assert tool is not None

    def test_returns_dict(self) -> None:
        """get_capabilities must return a dictionary."""
        tool = _get_tool("get_capabilities")
        result = tool.fn().data.model_dump()
        assert isinstance(result, dict)

    def test_has_name(self) -> None:
        """Capabilities must include brick name."""
        tool = _get_tool("get_capabilities")
        result = tool.fn().data.model_dump()
        assert "name" in result
        assert result["name"] == "evals"

    def test_has_version(self) -> None:
        """Capabilities must include version."""
        tool = _get_tool("get_capabilities")
        result = tool.fn().data.model_dump()
        assert "version" in result

    def test_has_backends(self) -> None:
        """Capabilities must list available backends."""
        tool = _get_tool("get_capabilities")
        result = tool.fn().data.model_dump()
        assert "backends" in result

    def test_has_features(self) -> None:
        """Capabilities must list features."""
        tool = _get_tool("get_capabilities")
        result = tool.fn().data.model_dump()
        assert "features" in result


class TestHealthCheck:
    """Tests for health_check contract tool."""

    def test_tool_registered(self) -> None:
        """health_check tool must be registered."""
        tool = _get_tool("health_check")
        assert tool is not None

    def test_returns_dict(self) -> None:
        """health_check must return a dictionary."""
        tool = _get_tool("health_check")
        result = tool.fn().data.model_dump()
        assert isinstance(result, dict)

    def test_has_healthy_field(self) -> None:
        """health_check must include healthy status."""
        tool = _get_tool("health_check")
        result = tool.fn().data.model_dump()
        assert "healthy" in result
        assert isinstance(result["healthy"], bool)


class TestDescribeConfigSchema:
    """Tests for describe_config_schema contract tool."""

    def test_tool_registered(self) -> None:
        """describe_config_schema tool must be registered."""
        tool = _get_tool("describe_config_schema")
        assert tool is not None

    def test_returns_dict(self) -> None:
        """describe_config_schema must return a dictionary."""
        tool = _get_tool("describe_config_schema")
        result = tool.fn().data.model_dump()
        assert isinstance(result, dict)

    def test_has_type_field(self) -> None:
        """Schema must have type field."""
        tool = _get_tool("describe_config_schema")
        result = tool.fn().data.model_dump()
        assert "type" in result
        assert result["type"] == "object"
