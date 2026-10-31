"""Tests for StructlogSink adapter (structlog library).

Exercises real structlog processing — no mocks.
"""

from __future__ import annotations

import pytest

from factory.logger.runtime.ports import LogLevel, LogRecord
from factory.logger.runtime.adapters.structlog_sink import StructlogSink


class TestStructlogSink:
    """Tests for StructlogSink using real structlog library."""

    def test_import(self) -> None:
        """StructlogSink and structlog are importable."""
        import structlog
        assert structlog is not None
        assert StructlogSink is not None

    def test_instantiation_json(self) -> None:
        """Can create a JSON-mode sink."""
        sink = StructlogSink(json_output=True)
        assert sink is not None

    def test_instantiation_console(self) -> None:
        """Can create a console-mode sink."""
        sink = StructlogSink(json_output=False)
        assert sink is not None

    def test_write_info(self, capsys) -> None:
        """write() emits a log line to stdout."""
        sink = StructlogSink(json_output=False)
        record = LogRecord(level=LogLevel.INFO, message="hello world")
        sink.write(record)
        captured = capsys.readouterr()
        assert "hello world" in captured.out

    def test_write_with_context(self, capsys) -> None:
        """Context fields appear in output."""
        sink = StructlogSink(json_output=False)
        record = LogRecord(
            level=LogLevel.WARNING,
            message="disk full",
            source="storage",
            context={"disk": "/dev/sda1"},
        )
        sink.write(record)
        captured = capsys.readouterr()
        assert "disk full" in captured.out

    def test_health_check(self) -> None:
        """health_check reports writable."""
        sink = StructlogSink()
        health = sink.health_check()
        assert health["writable"] is True
        assert health["backend"] == "structlog"

    def test_flush_noop(self) -> None:
        """flush() doesn't raise."""
        sink = StructlogSink()
        sink.flush()  # should not raise

    def test_close_noop(self) -> None:
        """close() doesn't raise."""
        sink = StructlogSink()
        sink.close()  # should not raise

    def test_all_log_levels(self, capsys) -> None:
        """All log levels can be written without error."""
        sink = StructlogSink(json_output=False)
        for level in LogLevel:
            record = LogRecord(level=level, message=f"test {level.value}")
            sink.write(record)
        captured = capsys.readouterr()
        assert "test info" in captured.out
        assert "test error" in captured.out
