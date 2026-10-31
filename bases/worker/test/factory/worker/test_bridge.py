"""Tests for the Worker public MCP gateway bridge."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from factory.worker.runtime.bridge import execute_mcp_tool, list_mcp_tools, register_mcp_tasks
from factory.worker.runtime.bridge_policy import BridgePolicy


@pytest.fixture(autouse=True)
def catalog_metadata(monkeypatch):
    """Provide public category metadata for isolated fake-aggregator tests."""
    metadata = {
        "kb_search": {"category": "deterministic", "input_schema": {"properties": {}}},
        "known": {"category": "deterministic", "input_schema": {"properties": {}}},
        "missing": {"category": "deterministic", "input_schema": {"properties": {}}},
        "worker_get_capabilities": {"category": "deterministic", "input_schema": {"properties": {}}},
        "worker.authoring.set_config": {"category": "authoring", "input_schema": {"properties": {}}},
    }
    monkeypatch.setattr("factory.worker.runtime.bridge._tool_metadata", lambda: metadata)


class FakeAggregator:
    def __init__(self, names=None):
        self.names = names or ["kb_search", "worker.authoring.set_config"]
        self.invocations = []
        self.result = {"results": ["doc1"]}
        self.exception = None

    def get_all_tool_names(self):
        return list(self.names)

    def invoke_tool(self, tool_name, **kwargs):
        self.invocations.append((tool_name, kwargs))
        if self.exception is not None:
            raise self.exception
        return self.result


def test_execution_uses_public_aggregator_invocation_and_allowlist() -> None:
    aggregator = FakeAggregator()
    policy = BridgePolicy(allowlist=frozenset({"kb_search"}))
    with patch("factory.worker.runtime.bridge._get_mcp_server", return_value=aggregator):
        result = execute_mcp_tool(
            "kb_search", {"query": "test"}, principal_id="caller", policy=policy,
        )
    assert result == {"tool": "kb_search", "result": {"results": ["doc1"]}}
    assert aggregator.invocations == [("kb_search", {"query": "test"})]


def test_listing_and_execution_share_the_same_default_deny_policy() -> None:
    aggregator = FakeAggregator()
    policy = BridgePolicy(allowlist=frozenset({"kb_search"}))
    with patch("factory.worker.runtime.bridge._get_mcp_server", return_value=aggregator):
        listed = list_mcp_tools(principal_id="caller", policy=policy)
        allowed = execute_mcp_tool("kb_search", policy=policy)
        denied = execute_mcp_tool("worker.authoring.set_config", policy=policy)
    assert listed == {"tools": ["kb_search"], "count": 1, "error": None}
    assert allowed["tool"] == "kb_search"
    assert denied["error"] == "bridge_access_denied"


def test_dangerous_tools_require_an_explicit_privileged_principal() -> None:
    aggregator = FakeAggregator()
    policy = BridgePolicy(
        allowlist=frozenset({"worker.authoring.set_config"}),
        privileged_principals=frozenset({"operator"}),
    )
    with patch("factory.worker.runtime.bridge._get_mcp_server", return_value=aggregator):
        denied = execute_mcp_tool(
            "worker.authoring.set_config", principal_id="caller", policy=policy,
        )
        allowed = execute_mcp_tool(
            "worker.authoring.set_config", principal_id="operator", policy=policy,
        )
    assert denied["error"] == "bridge_access_denied"
    assert allowed["tool"] == "worker.authoring.set_config"


def test_missing_and_provider_failures_are_stable_and_redacted() -> None:
    aggregator = FakeAggregator(names=["known"])
    policy = BridgePolicy(allowlist=frozenset({"known", "missing"}))
    with patch("factory.worker.runtime.bridge._get_mcp_server", return_value=aggregator):
        missing = execute_mcp_tool("missing", policy=policy)
        aggregator.exception = RuntimeError("provider secret")
        failure = execute_mcp_tool("known", policy=policy)
    assert missing["error"] == "bridge_tool_not_found"
    assert failure["error"] == "bridge_invocation_failed"
    assert "provider secret" not in str(failure)


def test_result_bounds_are_enforced() -> None:
    aggregator = FakeAggregator()
    aggregator.result = object()
    policy = BridgePolicy(allowlist=frozenset({"kb_search"}))
    with patch("factory.worker.runtime.bridge._get_mcp_server", return_value=aggregator):
        result = execute_mcp_tool("kb_search", policy=policy)
    assert result["error"] == "bridge_result_unavailable"


def test_registers_celery_tasks() -> None:
    app = MagicMock()
    app.task = lambda *args, **kwargs: lambda fn: fn
    register_mcp_tasks(app)


def test_typed_tool_result_success_is_not_misclassified() -> None:
    from factory.mcp_utils.interface import ToolResult

    aggregator = FakeAggregator(names=["worker_get_capabilities"])
    aggregator.result = ToolResult(ok=True, data={"name": "worker"})
    policy = BridgePolicy(allowlist=frozenset({"worker_get_capabilities"}))
    with patch("factory.worker.runtime.bridge._get_mcp_server", return_value=aggregator):
        result = execute_mcp_tool("worker_get_capabilities", policy=policy)
    assert result["tool"] == "worker_get_capabilities"
    assert result["result"]["ok"] is True
    assert "error" not in result


def test_catalog_category_requires_privileged_principal() -> None:
    policy = BridgePolicy(allowlist=frozenset({"arbitrary_tool"}))
    assert not policy.decide("arbitrary_tool", "caller", category="operational").allowed
    assert policy.decide("arbitrary_tool", "operator", category="operational").allowed is False
    privileged = BridgePolicy(
        allowlist=frozenset({"arbitrary_tool"}),
        privileged_principals=frozenset({"operator"}),
    )
    assert privileged.decide("arbitrary_tool", "operator", category="operational").allowed


def test_missing_catalog_metadata_fails_closed() -> None:
    aggregator = FakeAggregator(names=["opaque"])
    policy = BridgePolicy(allowlist=frozenset({"opaque"}))
    with (
        patch("factory.worker.runtime.bridge._get_mcp_server", return_value=aggregator),
        patch("factory.worker.runtime.bridge._tool_metadata", return_value=None),
    ):
        assert execute_mcp_tool("opaque", policy=policy)["error"] == "bridge_unavailable"
        assert list_mcp_tools(policy=policy) == {
            "tools": [], "count": 0, "error": "bridge_unavailable",
        }


def test_unclassified_allowlisted_tool_is_not_executable() -> None:
    aggregator = FakeAggregator(names=["opaque"])
    policy = BridgePolicy(allowlist=frozenset({"opaque"}))
    with (
        patch("factory.worker.runtime.bridge._get_mcp_server", return_value=aggregator),
        patch("factory.worker.runtime.bridge._tool_metadata", return_value={}),
    ):
        assert execute_mcp_tool("opaque", policy=policy)["error"] == "bridge_access_denied"
        assert list_mcp_tools(policy=policy) == {
            "tools": [], "count": 0, "error": "bridge_access_denied",
        }


@pytest.mark.parametrize("category", ["", "deterministic_typo"])
def test_malformed_category_is_not_executable_or_listed(category) -> None:
    aggregator = FakeAggregator(names=["opaque"])
    policy = BridgePolicy(allowlist=frozenset({"opaque"}))
    with (
        patch("factory.worker.runtime.bridge._get_mcp_server", return_value=aggregator),
        patch(
            "factory.worker.runtime.bridge._tool_metadata",
            return_value={"opaque": {"category": category}},
        ),
    ):
        assert execute_mcp_tool("opaque", policy=policy)["error"] == "bridge_access_denied"
        assert list_mcp_tools(policy=policy) == {
            "tools": [], "count": 0, "error": "bridge_access_denied",
        }
