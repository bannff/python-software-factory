"""Tests for logger brick core types and formatters."""

from factory.logger.runtime.ports import LogLevel, LogRecord
from factory.logger.runtime.adapters import JsonFormatter, TextFormatter


class TestLogRecord:
    """Test LogRecord dataclass."""
    
    def test_create_record(self):
        record = LogRecord(level=LogLevel.INFO, message="Test message")
        assert record.level == LogLevel.INFO
        assert record.message == "Test message"
        assert record.logger_name == "factory"
    
    def test_record_with_context(self):
        record = LogRecord(
            level=LogLevel.ERROR,
            message="Error occurred",
            source="auth",
            run_id="run-123",
            context={"user_id": "abc"},
        )
        assert record.source == "auth"
        assert record.run_id == "run-123"
        assert record.context["user_id"] == "abc"


class TestJsonFormatter:
    """Test JSON formatter."""
    
    def test_format_basic(self):
        formatter = JsonFormatter()
        record = LogRecord(level=LogLevel.INFO, message="Hello")
        output = formatter.format(record)
        assert '"level": "info"' in output
        assert '"message": "Hello"' in output
    
    def test_format_with_context(self):
        formatter = JsonFormatter()
        record = LogRecord(
            level=LogLevel.WARNING,
            message="Warning",
            source="test",
            context={"key": "value"},
        )
        output = formatter.format(record)
        assert '"source": "test"' in output
        assert '"key": "value"' in output


class TestTextFormatter:
    """Test text formatter."""
    
    def test_format_basic(self):
        formatter = TextFormatter()
        record = LogRecord(level=LogLevel.INFO, message="Hello world")
        output = formatter.format(record)
        assert "INFO" in output
        assert "Hello world" in output
    
    def test_format_with_source(self):
        formatter = TextFormatter()
        record = LogRecord(level=LogLevel.ERROR, message="Error", source="auth")
        output = formatter.format(record)
        assert "source=auth" in output
