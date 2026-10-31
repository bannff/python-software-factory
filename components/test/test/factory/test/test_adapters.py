"""Tests for test brick adapters.

Tests both MemoryAdapter and PytestAdapter implementations.
"""

from __future__ import annotations

import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock
import sys
import time

from factory.test.runtime.adapters.bounded_subprocess import run_bounded
from factory.test.interface import (
    MemoryAdapter,
    PytestAdapter,
    MockTestCase,
    TestRunner,
)


class TestMemoryAdapterProtocol:
    """Tests for MemoryAdapter protocol compliance."""

    def test_implements_test_runner_protocol(self) -> None:
        """Test that MemoryAdapter implements TestRunner protocol."""
        adapter = MemoryAdapter()
        assert isinstance(adapter, TestRunner)

    def test_run_tests_returns_test_result(self) -> None:
        """Test that run_tests returns TestResult."""
        adapter = MemoryAdapter()
        result = adapter.run_tests(".")
        assert hasattr(result, "passed")
        assert hasattr(result, "failed")
        assert hasattr(result, "to_dict")

    def test_discover_tests_returns_discovery_result(self) -> None:
        """Test that discover_tests returns TestDiscoveryResult."""
        adapter = MemoryAdapter()
        result = adapter.discover_tests(".")
        assert hasattr(result, "test_files")
        assert hasattr(result, "test_count")
        assert hasattr(result, "to_dict")

    def test_health_check_returns_dict(self) -> None:
        """Test that health_check returns dict."""
        adapter = MemoryAdapter()
        result = adapter.health_check()
        assert isinstance(result, dict)
        assert "status" in result
        assert "backend" in result


class TestMemoryAdapterVerboseOutput:
    """Tests for MemoryAdapter verbose output."""

    def test_verbose_output_includes_test_names(self) -> None:
        """Test that verbose output includes test names."""
        adapter = MemoryAdapter()
        adapter.add_test_case(MockTestCase(
            name="test_example",
            file="test_example.py",
            status="passed",
        ))
        result = adapter.run_tests(".", verbose=True)
        assert "test_example" in result.output
        assert "PASSED" in result.output

    def test_non_verbose_output_is_compact(self) -> None:
        """Test that non-verbose output is compact."""
        adapter = MemoryAdapter()
        adapter.add_test_case(MockTestCase(
            name="test_example",
            file="test_example.py",
            status="passed",
        ))
        result = adapter.run_tests(".", verbose=False)
        assert "." in result.output
        assert "test_example" not in result.output


class TestPytestAdapterProtocol:
    """Tests for PytestAdapter protocol compliance."""

    def test_implements_test_runner_protocol(self) -> None:
        """Test that PytestAdapter implements TestRunner protocol."""
        adapter = PytestAdapter()
        assert isinstance(adapter, TestRunner)

    def test_root_dir_is_resolved(self) -> None:
        """Test that root_dir is resolved to absolute path."""
        adapter = PytestAdapter(".")
        assert adapter.root_dir.is_absolute()

    def test_health_check_returns_dict(self) -> None:
        """Test that health_check returns dict with expected keys."""
        adapter = PytestAdapter()
        result = adapter.health_check()
        assert isinstance(result, dict)
        assert "status" in result
        assert "backend" in result
        assert result["backend"] == "pytest"


class TestPytestAdapterPathHandling:
    """Tests for PytestAdapter path handling."""

    def test_run_tests_nonexistent_path(self) -> None:
        """Test that run_tests handles nonexistent paths."""
        adapter = PytestAdapter()
        result = adapter.run_tests("/nonexistent/path/that/does/not/exist")
        assert result.success is False
        assert "not found" in result.errors[0].lower() or "not exist" in result.output.lower()

    def test_discover_tests_nonexistent_path(self) -> None:
        """Test that discover_tests handles nonexistent paths."""
        adapter = PytestAdapter()
        result = adapter.discover_tests("/nonexistent/path/that/does/not/exist")
        assert len(result.errors) > 0


class TestPytestAdapterOutputParsing:
    """Tests for PytestAdapter output parsing."""

    def test_parse_pytest_output_all_passed(self) -> None:
        """Test parsing pytest output with all tests passed."""
        adapter = PytestAdapter()
        result = adapter._parse_pytest_output(
            stdout="5 passed in 1.23s",
            stderr="",
            returncode=0,
            duration=1.23,
        )
        assert result.passed == 5
        assert result.failed == 0
        assert result.success is True

    def test_parse_pytest_output_with_failures(self) -> None:
        """Test parsing pytest output with failures."""
        adapter = PytestAdapter()
        result = adapter._parse_pytest_output(
            stdout="3 passed, 2 failed in 2.5s",
            stderr="",
            returncode=1,
            duration=2.5,
        )
        assert result.passed == 3
        assert result.failed == 2
        assert result.success is False

    def test_parse_pytest_output_with_skipped(self) -> None:
        """Test parsing pytest output with skipped tests."""
        adapter = PytestAdapter()
        result = adapter._parse_pytest_output(
            stdout="4 passed, 1 skipped in 1.0s",
            stderr="",
            returncode=0,
            duration=1.0,
        )
        assert result.passed == 4
        assert result.skipped == 1
        assert result.success is True

    def test_parse_pytest_output_nonzero_exit_no_failures(self) -> None:
        """Test parsing pytest output with nonzero exit but no failures."""
        adapter = PytestAdapter()
        result = adapter._parse_pytest_output(
            stdout="",
            stderr="Error: no tests collected",
            returncode=5,
            duration=0.1,
        )
        assert len(result.errors) > 0

    def test_parse_collect_output(self) -> None:
        """Test parsing pytest --collect-only output."""
        adapter = PytestAdapter()
        result = adapter._parse_collect_output(
            stdout="test_a.py::test_one\ntest_a.py::test_two\ntest_b.py::test_three",
            stderr="",
        )
        assert result.test_count == 3
        assert len(result.test_files) == 2
        assert "test_a.py" in result.test_files
        assert "test_b.py" in result.test_files

    def test_parse_collect_output_with_false_positive_error_text(self) -> None:
        """Node IDs containing error words are still successful collection output."""
        adapter = PytestAdapter()
        result = adapter._parse_collect_output(
            stdout="test_error.py::test_no_error\n", stderr="", returncode=0
        )
        assert result.test_count == 1
        assert result.test_files == ["test_error.py"]
        assert result.errors == []

    def test_parse_collect_output_uses_exit_code_for_collection_errors(self) -> None:
        """Collection failures remain errors even when valid nodes precede them."""
        adapter = PytestAdapter()
        result = adapter._parse_collect_output(
            stdout=("test_ok.py::test_ok\n"
                    "ERROR collecting broken.py\n"
                    "E   ImportError: broken dependency\n"),
            stderr="",
            returncode=2,
        )
        assert result.test_count == 1
        assert result.errors


def test_bounded_subprocess_capture_and_timeout_cleanup(tmp_path) -> None:
    captured = run_bounded(
        [sys.executable, "-c", "print('x' * 10000)"],
        cwd=tmp_path,
        timeout=5,
        max_output=1024,
    )
    assert captured.error is None
    assert captured.timed_out is False
    assert captured.truncated is True
    assert len(captured.output.encode()) <= 1024

    started = time.monotonic()
    timed_out = run_bounded(
        [sys.executable, "-c", "import time; time.sleep(5)"],
        cwd=tmp_path,
        timeout=0.1,
    )
    assert timed_out.timed_out is True
    assert time.monotonic() - started < 2


def test_memory_adapter_honors_path_and_pattern_filters() -> None:
    adapter = MemoryAdapter()
    adapter.add_test_cases([
        MockTestCase(name="test_default", file="components/example/test/test_unit.py"),
        MockTestCase(name="test_spec", file="components/example/test/spec_unit.py"),
        MockTestCase(name="test_other", file="components/other/test/spec_other.py"),
    ])
    discovered = adapter.discover_tests("components/example/test", "spec_*.py")
    assert discovered.test_count == 1
    assert discovered.test_files == ["components/example/test/spec_unit.py"]
    qualified = adapter.discover_tests(".", "components/example/test/spec_*.py")
    assert qualified.test_count == 1
    result = adapter.run_tests("components/example/test", "spec_*.py")
    assert result.passed == 1 and result.failed == 0
    assert result.test_files == discovered.test_files


def test_pytest_adapter_honors_explicit_pattern(tmp_path) -> None:
    (tmp_path / "test_default.py").write_text("def test_default(): pass\n", encoding="utf-8")
    (tmp_path / "spec_explicit.py").write_text("def test_explicit(): pass\n", encoding="utf-8")
    adapter = PytestAdapter(str(tmp_path))
    discovered = adapter.discover_tests(".", "spec_*.py")
    assert discovered.test_count == 1
    assert discovered.test_files == ["spec_explicit.py"]
    result = adapter.run_tests(".", "spec_*.py")
    assert result.passed == 1 and result.failed == 0

    mismatch = adapter.run_tests("test_default.py", "spec_*.py")
    assert mismatch.errors == []
    assert mismatch.passed == 0 and mismatch.failed == 0

    nested = tmp_path / "nested"
    nested.mkdir()
    (nested / "spec_nested.py").write_text("def test_nested(): pass\n", encoding="utf-8")
    qualified = adapter.discover_tests(".", "nested/spec_*.py")
    assert qualified.test_count == 1
    assert any(item.endswith("nested/spec_nested.py") for item in qualified.test_files)
