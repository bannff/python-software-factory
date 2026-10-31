"""Tests for the MemoryAdapter."""

import pytest

# Import from interface to avoid namespace shadowing
from factory.test.interface import MemoryAdapter, MockTestCase


class TestMemoryAdapter:
    """Tests for MemoryAdapter."""

    def test_empty_adapter_returns_no_tests(self):
        """Test that empty adapter returns no tests."""
        adapter = MemoryAdapter()
        result = adapter.run_tests(".")
        assert result.total == 0
        assert result.success is True

    def test_add_passing_test(self):
        """Test adding a passing test case."""
        adapter = MemoryAdapter()
        adapter.add_test_case(MockTestCase(
            name="test_example",
            file="test_example.py",
            status="passed",
            duration=0.1,
        ))
        result = adapter.run_tests(".")
        assert result.passed == 1
        assert result.failed == 0
        assert result.success is True

    def test_add_failing_test(self):
        """Test adding a failing test case."""
        adapter = MemoryAdapter()
        adapter.add_test_case(MockTestCase(
            name="test_fail",
            file="test_fail.py",
            status="failed",
            error_message="AssertionError",
        ))
        result = adapter.run_tests(".")
        assert result.passed == 0
        assert result.failed == 1
        assert result.success is False
        assert "AssertionError" in result.errors

    def test_mixed_results(self):
        """Test mixed pass/fail/skip results."""
        adapter = MemoryAdapter()
        adapter.add_test_cases([
            MockTestCase(name="test_pass", file="test_a.py", status="passed"),
            MockTestCase(name="test_fail", file="test_a.py", status="failed"),
            MockTestCase(name="test_skip", file="test_a.py", status="skipped"),
        ])
        result = adapter.run_tests(".")
        assert result.passed == 1
        assert result.failed == 1
        assert result.skipped == 1
        assert result.total == 3

    def test_path_filtering(self):
        """Test that path filtering works."""
        adapter = MemoryAdapter()
        adapter.add_test_cases([
            MockTestCase(name="test_a", file="components/auth/test_auth.py", status="passed"),
            MockTestCase(name="test_b", file="components/kb/test_kb.py", status="passed"),
        ])
        result = adapter.run_tests("components/auth")
        assert result.passed == 1
        assert result.test_files == ["components/auth/test_auth.py"]

    def test_discover_tests(self):
        """Test test discovery."""
        adapter = MemoryAdapter()
        adapter.add_test_cases([
            MockTestCase(name="test_a", file="test_a.py", status="passed"),
            MockTestCase(name="test_b", file="test_a.py", status="passed"),
            MockTestCase(name="test_c", file="test_b.py", status="passed"),
        ])
        result = adapter.discover_tests(".")
        assert result.test_count == 3
        assert len(result.test_files) == 2

    def test_health_check_healthy(self):
        """Test health check when healthy."""
        adapter = MemoryAdapter()
        health = adapter.health_check()
        assert health["status"] == "healthy"
        assert health["backend"] == "memory"

    def test_health_check_unhealthy(self):
        """Test health check when unhealthy."""
        adapter = MemoryAdapter()
        adapter.set_healthy(False)
        health = adapter.health_check()
        assert health["status"] == "unhealthy"

    def test_clear_test_cases(self):
        """Test clearing test cases."""
        adapter = MemoryAdapter()
        adapter.add_test_case(MockTestCase(name="test", file="test.py", status="passed"))
        adapter.clear_test_cases()
        result = adapter.run_tests(".")
        assert result.total == 0
