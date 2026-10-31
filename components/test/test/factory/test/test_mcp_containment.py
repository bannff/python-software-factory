"""Regression tests for Test MCP containment and trusted direct JUnit access."""
from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from factory.test.interface import TestResult, TestRuntime
from factory.test.runtime.mcp_containment import ContainmentError, McpTestRuntime
from factory.test.runtime.junit_fixtures import case, write_report


def test_facade_init_uses_root_without_health_or_info(tmp_path) -> None:
    runtime = TestRuntime(root_dir=tmp_path, adapter_type="memory")
    runtime.health_check = MagicMock(side_effect=AssertionError("health must not run"))
    runtime.get_info = MagicMock(side_effect=AssertionError("info must not run"))
    facade = McpTestRuntime(runtime)
    assert facade is not None
    runtime.health_check.assert_not_called()
    runtime.get_info.assert_not_called()


@pytest.mark.parametrize(
    "path",
    ["", "\x00", "/tmp/outside", "../outside", "nested/../outside", "./nested",
     "nested//file", "nested\\file", "C:outside"],
)
def test_invalid_paths_are_rejected_before_adapter_entry(tmp_path, path) -> None:
    runtime = TestRuntime(root_dir=tmp_path, adapter_type="memory")
    runtime.run_tests = MagicMock(side_effect=AssertionError("adapter must not run"))
    with pytest.raises(ContainmentError):
        McpTestRuntime(runtime).run_path(path, "test_*.py", False)
    runtime.run_tests.assert_not_called()


def test_valid_contained_target_is_root_relative_and_calls_adapter(tmp_path) -> None:
    target = tmp_path / "nested"
    target.mkdir()
    runtime = TestRuntime(root_dir=tmp_path, adapter_type="memory")
    runtime.run_tests = MagicMock(return_value=TestResult(passed=1, test_files=["nested/test_one.py"]))
    result = McpTestRuntime(runtime).run_path("nested", "test_*.py", False)
    runtime.run_tests.assert_called_once_with("nested", "test_*.py", False)
    assert result["target"] == "nested"
    assert result["test_files"] == ["nested/test_one.py"]


def test_symlink_target_and_intermediate_are_rejected(tmp_path) -> None:
    outside = tmp_path.parent / f"test-outside-{tmp_path.name}"
    outside.mkdir()
    link = tmp_path / "link"
    try:
        link.symlink_to(outside, target_is_directory=True)
    except OSError:
        pytest.skip("symlinks unavailable")
    facade = McpTestRuntime(TestRuntime(root_dir=tmp_path, adapter_type="memory"))
    with pytest.raises(ContainmentError, match="unsafe_path"):
        facade.run_path("link", "test_*.py", False)
    with pytest.raises(ContainmentError, match="unsafe_path"):
        facade.run_path("link/child", "test_*.py", False)


def test_junit_outside_root_is_rejected_but_direct_api_remains_unrestricted(tmp_path) -> None:
    root = tmp_path / "root"
    root.mkdir()
    base = write_report(tmp_path / "base.xml", case("test_old", "failure"))
    candidate = write_report(tmp_path / "candidate.xml", case("test_old"))
    runtime = TestRuntime(root_dir=root, adapter_type="memory")
    runtime.compare_junit = MagicMock(side_effect=AssertionError("MCP must reject first"))
    with pytest.raises(ContainmentError):
        McpTestRuntime(runtime).compare_junit(base, candidate)
    runtime.compare_junit.assert_not_called()

    direct = TestRuntime(root_dir=root, adapter_type="memory").compare_junit(base, candidate)
    assert direct["passed"] is True
    assert direct["resolved"][0]["reason"] == "executed_and_passed"


@pytest.mark.parametrize(
    "pattern",
    ["", " ", ".", "..", "../bad", "/tmp/bad", "~/bad", "C:/bad", "foo\\bar", "bad\x00"],
)
def test_invalid_patterns_are_rejected_before_adapter_entry(tmp_path, pattern) -> None:
    target = tmp_path / "target"
    target.mkdir()
    runtime = TestRuntime(root_dir=tmp_path, adapter_type="memory")
    runtime.run_tests = MagicMock(side_effect=AssertionError("adapter must not run"))
    with pytest.raises(ContainmentError, match="invalid_pattern"):
        McpTestRuntime(runtime).run_path("target", pattern, False)
    runtime.run_tests.assert_not_called()
