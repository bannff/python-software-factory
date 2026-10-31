"""Regression tests for truthful Test-brick authoring state."""
from __future__ import annotations

import asyncio
from unittest.mock import MagicMock

import pytest

from factory.test.interface import TestDiscoveryResult, TestResult, TestRuntime, create_server


def _tool(mcp, name: str):
    return asyncio.run(mcp.get_tool(name))


def test_authoring_status_and_mutations_update_runtime_state(tmp_path) -> None:
    runtime = TestRuntime(root_dir=tmp_path, adapter_type="memory")
    mcp = create_server(runtime)
    status = _tool(mcp, "test_authoring_get_status").fn()
    assert status.ok and status.data.enabled is True
    assert status.data.adapter == "memory"
    assert status.data.pattern == "test_*.py"

    assert _tool(mcp, "test_authoring_set_adapter").fn(adapter="pytest").data.success is True
    assert _tool(mcp, "test_authoring_set_timeout").fn(timeout_seconds=12).data.success is True
    assert _tool(mcp, "test_authoring_set_pattern").fn(pattern="spec_*.py").data.success is True
    assert _tool(mcp, "test_authoring_set_verbose").fn(verbose=True).data.success is True

    status = _tool(mcp, "test_authoring_get_status").fn()
    assert status.data.adapter == "pytest"
    assert status.data.timeout_seconds == 12
    assert status.data.pattern == "spec_*.py"
    assert status.data.verbose is True


def test_authoring_defaults_affect_later_mcp_execution(tmp_path) -> None:
    target = tmp_path / "target"
    target.mkdir()
    runtime = TestRuntime(root_dir=tmp_path, adapter_type="memory")
    mcp = create_server(runtime)
    _tool(mcp, "test_authoring_set_pattern").fn(pattern="spec_*.py")
    _tool(mcp, "test_authoring_set_verbose").fn(verbose=True)

    adapter = MagicMock()
    adapter.run_tests.return_value = TestResult(passed=1)
    runtime.set_adapter(adapter)
    result = _tool(mcp, "test_run_path").fn(path="target")
    assert result.ok and result.data.success is True
    adapter.run_tests.assert_called_once_with("target", "spec_*.py", True)


def test_invalid_authoring_values_are_typed_domain_negatives(tmp_path) -> None:
    mcp = create_server(TestRuntime(root_dir=tmp_path, adapter_type="memory"))
    for name, kwargs, error in (
        ("test_authoring_set_adapter", {"adapter": "unknown"}, "invalid_adapter"),
        ("test_authoring_set_timeout", {"timeout_seconds": 0}, "invalid_timeout"),
        ("test_authoring_set_pattern", {"pattern": "../bad"}, "invalid_pattern"),
    ):
        result = _tool(mcp, name).fn(**kwargs)
        assert result.ok is True
        assert result.data.success is False
        assert result.data.error == error



def test_explicit_mcp_defaults_override_authored_defaults(tmp_path) -> None:
    target = tmp_path / "target"
    target.mkdir()
    runtime = TestRuntime(root_dir=tmp_path, adapter_type="memory")
    mcp = create_server(runtime)
    _tool(mcp, "test_authoring_set_pattern").fn(pattern="spec_*.py")
    _tool(mcp, "test_authoring_set_verbose").fn(verbose=True)
    adapter = MagicMock()
    adapter.run_tests.return_value = TestResult(passed=1)
    runtime.set_adapter(adapter)

    result = _tool(mcp, "test_run_path").fn(
        path="target", pattern="test_*.py", verbose=False
    )
    assert result.ok and result.data.success is True
    adapter.run_tests.assert_called_once_with("target", "test_*.py", False)



def test_explicit_discover_default_pattern_is_not_authored_pattern(tmp_path) -> None:
    target = tmp_path / "target"
    target.mkdir()
    runtime = TestRuntime(root_dir=tmp_path, adapter_type="memory")
    mcp = create_server(runtime)
    _tool(mcp, "test_authoring_set_pattern").fn(pattern="spec_*.py")
    runtime.discover_tests = MagicMock(return_value=TestDiscoveryResult())

    result = _tool(mcp, "test_discover").fn(path="target", pattern="test_*.py")
    assert result.ok
    runtime.discover_tests.assert_called_once_with("target", "test_*.py")


@pytest.mark.parametrize(
    "pattern",
    ["", " ", ".", "..", "../bad", "/tmp/bad", "~/bad", "C:/bad", "foo\\bar", "bad\x00"],
)
def test_invalid_authored_patterns_preserve_state(tmp_path, pattern) -> None:
    mcp = create_server(TestRuntime(root_dir=tmp_path, adapter_type="memory"))
    _tool(mcp, "test_authoring_set_pattern").fn(pattern="spec_*.py")
    result = _tool(mcp, "test_authoring_set_pattern").fn(pattern=pattern)
    status = _tool(mcp, "test_authoring_get_status").fn()
    assert result.ok and result.data.error == "invalid_pattern"
    assert status.data.pattern == "spec_*.py"


def test_explicit_defaults_override_authored_defaults(tmp_path) -> None:
    target = tmp_path / "target"
    target.mkdir()
    runtime = TestRuntime(root_dir=tmp_path, adapter_type="memory")
    mcp = create_server(runtime)
    _tool(mcp, "test_authoring_set_pattern").fn(pattern="spec_*.py")
    _tool(mcp, "test_authoring_set_verbose").fn(verbose=True)

    adapter = MagicMock()
    adapter.run_tests.return_value = TestResult(passed=1)
    runtime.set_adapter(adapter)
    _tool(mcp, "test_run_path").fn(
        path="target", pattern="test_*.py", verbose=False
    )
    _tool(mcp, "test_run_path").fn(path="target")

    assert adapter.run_tests.call_args_list[0].args == ("target", "test_*.py", False)
    assert adapter.run_tests.call_args_list[1].args == ("target", "spec_*.py", True)
