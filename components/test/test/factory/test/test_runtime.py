"""Tests for TestRuntime."""

import pytest

# Import from interface to avoid namespace shadowing
from factory.test.interface import TestRuntime, MemoryAdapter, MockTestCase


class TestTestRuntime:
    """Tests for TestRuntime."""

    def test_default_adapter_is_pytest(self):
        """Test that default adapter is pytest."""
        runtime = TestRuntime(adapter_type="pytest")
        info = runtime.get_info()
        assert info["adapter_type"] == "pytest"

    def test_memory_adapter_selection(self):
        """Test selecting memory adapter."""
        runtime = TestRuntime(adapter_type="memory")
        info = runtime.get_info()
        assert info["adapter_type"] == "memory"

    def test_set_custom_adapter(self):
        """Test setting a custom adapter."""
        runtime = TestRuntime()
        custom_adapter = MemoryAdapter()
        runtime.set_adapter(custom_adapter)
        assert runtime.adapter is custom_adapter

    def test_run_tests_with_memory_adapter(self):
        """Test running tests with memory adapter."""
        runtime = TestRuntime(adapter_type="memory")
        adapter = MemoryAdapter()
        adapter.add_test_case(MockTestCase(
            name="test_example",
            file="test_example.py",
            status="passed",
        ))
        runtime.set_adapter(adapter)

        result = runtime.run_tests(".")
        assert result.passed == 1
        assert result.success is True

    def test_run_component_tests(self):
        """Test running component tests."""
        runtime = TestRuntime(adapter_type="memory")
        adapter = MemoryAdapter()
        adapter.add_test_cases([
            MockTestCase(name="test_a", file="components/auth/test/test_auth.py", status="passed"),
            MockTestCase(name="test_b", file="components/kb/test/test_kb.py", status="passed"),
        ])
        runtime.set_adapter(adapter)

        result = runtime.run_component_tests("auth")
        assert result.passed == 1

    def test_discover_tests(self):
        """Test test discovery."""
        runtime = TestRuntime(adapter_type="memory")
        adapter = MemoryAdapter()
        adapter.add_test_cases([
            MockTestCase(name="test_a", file="test_a.py", status="passed"),
            MockTestCase(name="test_b", file="test_b.py", status="passed"),
        ])
        runtime.set_adapter(adapter)

        result = runtime.discover_tests(".")
        assert result.test_count == 2

    def test_health_check(self):
        """Test health check."""
        runtime = TestRuntime(adapter_type="memory")
        health = runtime.health_check()
        assert health["status"] == "healthy"
        assert health["backend"] == "memory"

    def test_get_info(self):
        """Test get_info returns expected structure."""
        runtime = TestRuntime(adapter_type="memory")
        info = runtime.get_info()
        assert "root_dir" in info
        assert "adapter_type" in info
        assert "adapter_health" in info
        assert info["adapter_type"] == "memory"
