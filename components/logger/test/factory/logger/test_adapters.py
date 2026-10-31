"""Tests for logger adapters (sinks and queries)."""

import tempfile
from pathlib import Path

from factory.logger.runtime.ports import LogLevel, LogRecord
from factory.logger.runtime.adapters import FileSink, FileQuery


class TestFileSink:
    """Test file sink adapter."""
    
    def test_write_and_health_check(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            sink = FileSink(log_dir=tmpdir, filename="test.log")
            record = LogRecord(level=LogLevel.INFO, message="Test")
            
            sink.write(record)
            sink.flush()
            
            health = sink.health_check()
            assert health["sink"] == "file"
            assert health["exists"] is True
            assert health["writable"] is True
            
            sink.close()


class TestFileQuery:
    """Test file query adapter."""
    
    def test_tail_empty(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            query = FileQuery(Path(tmpdir) / "nonexistent.log")
            result = query.tail(n=10)
            assert result == []
    
    def test_tail_with_entries(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            log_file = Path(tmpdir) / "test.log"
            sink = FileSink(log_dir=tmpdir, filename="test.log")
            
            for i in range(5):
                record = LogRecord(level=LogLevel.INFO, message=f"Message {i}")
                sink.write(record)
            sink.flush()
            sink.close()
            
            query = FileQuery(log_file)
            result = query.tail(n=3)
            assert len(result) == 3
            assert result[-1].message == "Message 4"
