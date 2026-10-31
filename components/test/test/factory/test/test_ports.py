"""Tests for test brick ports (protocols and data classes)."""

import pytest

# Import from interface to avoid namespace shadowing
from factory.test.interface import (
    TestResult,
    TestDiscoveryResult,
    TestRunner,
)


class TestTestResult:
    """Tests for TestResult dataclass."""

    def test_default_values(self):
        """Test default values are set correctly."""
        result = TestResult()
        assert result.passed == 0
        assert result.failed == 0
        assert result.skipped == 0
        assert result.duration == 0.0
        assert result.output == ""
        assert result.errors == []
        assert result.test_files == []

    def test_total_property(self):
        """Test total property calculates correctly."""
        result = TestResult(passed=5, failed=2, skipped=1)
        assert result.total == 8

    def test_success_property_when_no_failures(self):
        """Test success is True when no failures."""
        result = TestResult(passed=5, failed=0, skipped=1)
        assert result.success is True

    def test_success_property_when_errors(self):
        """Test adapter errors cannot masquerade as a pass."""
        result = TestResult(errors=["adapter_error"])
        assert result.success is False

    def test_to_dict(self):
        """Test to_dict returns correct structure."""
        result = TestResult(
            passed=3,
            failed=1,
            skipped=2,
            duration=1.5,
            output="test output",
            errors=["error1"],
            test_files=["test_a.py"],
        )
        d = result.to_dict()
        assert d["passed"] == 3
        assert d["failed"] == 1
        assert d["skipped"] == 2
        assert d["total"] == 6
        assert d["duration"] == 1.5
        assert d["success"] is False
        assert d["output"] == "test output"
        assert d["errors"] == ["error1"]
        assert d["test_files"] == ["test_a.py"]


class TestTestDiscoveryResult:
    """Tests for TestDiscoveryResult dataclass."""

    def test_default_values(self):
        """Test default values are set correctly."""
        result = TestDiscoveryResult()
        assert result.test_files == []
        assert result.test_count == 0
        assert result.errors == []

    def test_to_dict(self):
        """Test to_dict returns correct structure."""
        result = TestDiscoveryResult(
            test_files=["test_a.py", "test_b.py"],
            test_count=10,
            errors=[],
        )
        d = result.to_dict()
        assert d["test_files"] == ["test_a.py", "test_b.py"]
        assert d["test_count"] == 10
        assert d["errors"] == []


class TestTestRunnerProtocol:
    """Tests for TestRunner protocol."""

    def test_protocol_is_runtime_checkable(self):
        """Test that TestRunner is runtime checkable."""
        from factory.test.interface import MemoryAdapter, PytestAdapter

        assert isinstance(MemoryAdapter(), TestRunner)
        assert isinstance(PytestAdapter(), TestRunner)
