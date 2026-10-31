"""Tests for log formatters."""

from __future__ import annotations

import json
from datetime import datetime

import pytest

from factory.logger.runtime.adapters.json_formatter import JsonFormatter
from factory.logger.runtime.adapters.text_formatter import TextFormatter
from factory.logger.runtime.ports import LogLevel, LogRecord


class TestJsonFormatter:
    """Tests for JsonFormatter."""

    def test_format_basic(self) -> None:
        """JsonFormatter produces valid JSON."""
        formatter = JsonFormatter()
        record = LogRecord(
            level=LogLevel.INFO,
            message="test message",
            timestamp=datetime(2024, 1, 1, 12, 0, 0),
            logger_name="test",
        )
        output = formatter.format(record)
        data = json.loads(output)
        assert data["level"] == "info"
        assert data["message"] == "test message"
        assert data["logger"] == "test"

    def test_format_with_context(self) -> None:
        """JsonFormatter includes context."""
        formatter = JsonFormatter()
        record = LogRecord(
            level=LogLevel.DEBUG,
            message="debug",
            timestamp=datetime.now(),
            logger_name="test",
            context={"key": "value"},
        )
        output = formatter.format(record)
        data = json.loads(output)
        assert data["context"] == {"key": "value"}

    def test_format_pretty(self) -> None:
        """JsonFormatter pretty mode adds indentation."""
        formatter = JsonFormatter(pretty=True)
        record = LogRecord(
            level=LogLevel.INFO,
            message="test",
            timestamp=datetime.now(),
            logger_name="test",
        )
        output = formatter.format(record)
        assert "\n" in output  # Pretty print has newlines

    def test_format_optional_fields(self) -> None:
        """JsonFormatter includes optional fields when present."""
        formatter = JsonFormatter()
        record = LogRecord(
            level=LogLevel.INFO,
            message="test",
            timestamp=datetime.now(),
            logger_name="test",
            source="my_module",
            run_id="run-123",
            tenant_id="tenant-456",
        )
        output = formatter.format(record)
        data = json.loads(output)
        assert data["source"] == "my_module"
        assert data["run_id"] == "run-123"
        assert data["tenant_id"] == "tenant-456"


class TestTextFormatter:
    """Tests for TextFormatter."""

    def test_format_basic(self) -> None:
        """TextFormatter produces readable text."""
        formatter = TextFormatter()
        record = LogRecord(
            level=LogLevel.INFO,
            message="test message",
            timestamp=datetime(2024, 1, 1, 12, 0, 0),
            logger_name="test",
        )
        output = formatter.format(record)
        assert "INFO" in output
        assert "test message" in output

    def test_format_includes_timestamp(self) -> None:
        """TextFormatter includes timestamp."""
        formatter = TextFormatter()
        record = LogRecord(
            level=LogLevel.ERROR,
            message="error occurred",
            timestamp=datetime(2024, 6, 15, 10, 30, 0),
            logger_name="app",
        )
        output = formatter.format(record)
        assert "2024" in output
        assert "ERROR" in output
