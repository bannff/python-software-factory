"""Tests for UI assertions."""

import pytest

from factory.evals.runtime.ui import (
    ConsoleClean,
    NetworkOK,
    A11yValid,
    PerformanceBudget,
    ElementExists,
)


class TestUIAssertions:
    """Tests for UI assertions."""

    def test_console_clean_passes(self):
        """Console clean passes with no errors."""
        assertion = ConsoleClean()
        context = {"console_messages": []}
        result = assertion.check(context)
        
        assert result.passed is True

    def test_console_clean_fails(self):
        """Console clean fails with errors."""
        assertion = ConsoleClean(max_errors=0)
        context = {
            "console_messages": [
                {"type": "error", "text": "Uncaught TypeError"},
            ]
        }
        result = assertion.check(context)
        
        assert result.passed is False
        assert "1 errors" in result.message

    def test_console_clean_ignore_patterns(self):
        """Console clean ignores specified patterns."""
        assertion = ConsoleClean(ignore_patterns=["favicon"])
        context = {
            "console_messages": [
                {"type": "error", "text": "Failed to load favicon.ico"},
            ]
        }
        result = assertion.check(context)
        
        assert result.passed is True

    def test_network_ok_passes(self):
        """Network OK passes with successful requests."""
        assertion = NetworkOK()
        context = {
            "network_requests": [
                {"url": "/api/data", "status": 200},
            ]
        }
        result = assertion.check(context)
        
        assert result.passed is True

    def test_network_ok_fails(self):
        """Network OK fails with failed requests."""
        assertion = NetworkOK()
        context = {
            "network_requests": [
                {"url": "/api/data", "status": 500},
            ]
        }
        result = assertion.check(context)
        
        assert result.passed is False

    def test_network_ok_allowed_failures(self):
        """Network OK allows specified failures."""
        assertion = NetworkOK(allowed_failures=["analytics"])
        context = {
            "network_requests": [
                {"url": "/analytics/track", "status": 500},
            ]
        }
        result = assertion.check(context)
        
        assert result.passed is True

    def test_a11y_valid_passes(self):
        """A11y valid passes with good snapshot."""
        assertion = A11yValid()
        context = {"snapshot": "button name='Submit'"}
        result = assertion.check(context)
        
        assert result.passed is True

    def test_a11y_valid_missing_landmark(self):
        """A11y valid fails with missing landmark."""
        assertion = A11yValid(required_landmarks=["navigation"])
        context = {"snapshot": "main content"}
        result = assertion.check(context)
        
        assert result.passed is False

    def test_performance_budget_passes(self):
        """Performance budget passes within limits."""
        assertion = PerformanceBudget(lcp_ms=2500)
        context = {"performance": {"lcp": 2000}}
        result = assertion.check(context)
        
        assert result.passed is True

    def test_performance_budget_fails(self):
        """Performance budget fails over limits."""
        assertion = PerformanceBudget(lcp_ms=2500)
        context = {"performance": {"lcp": 3000}}
        result = assertion.check(context)
        
        assert result.passed is False

    def test_element_exists_passes(self):
        """Element exists passes when found."""
        assertion = ElementExists(text="Welcome")
        context = {"snapshot": "Welcome to the app"}
        result = assertion.check(context)
        
        assert result.passed is True

    def test_element_exists_fails(self):
        """Element exists fails when not found."""
        assertion = ElementExists(text="Goodbye")
        context = {"snapshot": "Welcome to the app"}
        result = assertion.check(context)
        
        assert result.passed is False
