"""Tests for file adapter - FileSink and FileQuery."""

from __future__ import annotations

import tempfile
from datetime import datetime
from pathlib import Path

import pytest

from factory.logger.runtime.adapters.file_adapter import FileSink, FileQuery
from factory.logger.runtime.ports import LogLevel, LogRecord


class TestFileSink:
    """Tests for FileSink."""

    def test_write_creates_file(self, tmp_path: Path) -> None:
        """FileSink creates log file on write."""
        sink = FileSink(log_dir=tmp_path, filename="test.log")
        record = LogRecord(
            level=LogLevel.INFO,
            message="test message",
            timestamp=datetime.now(),
            logger_name="test",
        )
        sink.write(record)
        sink.flush()
        sink.close()
        assert (tmp_path / "test.log").exists()

    def test_write_appends(self, tmp_path: Path) -> None:
        """FileSink appends to existing file."""
        sink = FileSink(log_dir=tmp_path, filename="test.log")
        for i in range(3):
            record = LogRecord(
                level=LogLevel.INFO,
                message=f"message {i}",
                timestamp=datetime.now(),
                logger_name="test",
            )
            sink.write(record)
        sink.flush()
        sink.close()
        
        with open(tmp_path / "test.log") as f:
            lines = f.readlines()
        assert len(lines) == 3

    def test_health_check(self, tmp_path: Path) -> None:
        """FileSink health_check returns status."""
        sink = FileSink(log_dir=tmp_path, filename="test.log")
        health = sink.health_check()
        assert health["sink"] == "file"
        assert health["writable"] is True


class TestFileQuery:
    """Tests for FileQuery."""

    def test_tail_empty_file(self, tmp_path: Path) -> None:
        """FileQuery.tail returns empty for missing file."""
        query = FileQuery(tmp_path / "missing.log")
        assert query.tail() == []

    def test_tail_returns_records(self, tmp_path: Path) -> None:
        """FileQuery.tail returns last n records."""
        log_file = tmp_path / "test.log"
        sink = FileSink(log_dir=tmp_path, filename="test.log")
        for i in range(5):
            record = LogRecord(
                level=LogLevel.INFO,
                message=f"message {i}",
                timestamp=datetime.now(),
                logger_name="test",
            )
            sink.write(record)
        sink.flush()
        sink.close()
        
        query = FileQuery(log_file)
        results = query.tail(n=3)
        assert len(results) == 3
        assert results[-1].message == "message 4"

    def test_search_by_level(self, tmp_path: Path) -> None:
        """FileQuery.search filters by level."""
        log_file = tmp_path / "test.log"
        sink = FileSink(log_dir=tmp_path, filename="test.log")
        
        for level in [LogLevel.INFO, LogLevel.ERROR, LogLevel.INFO]:
            record = LogRecord(
                level=level,
                message=f"{level.value} message",
                timestamp=datetime.now(),
                logger_name="test",
            )
            sink.write(record)
        sink.flush()
        sink.close()
        
        query = FileQuery(log_file)
        results = query.search(level=LogLevel.ERROR)
        assert len(results) == 1
        assert results[0].level == LogLevel.ERROR
