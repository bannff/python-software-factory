"""Tests for context envelope."""

import pytest

from factory.events.runtime.envelope import ContextEnvelope


class TestContextEnvelope:
    """Tests for ContextEnvelope model."""

    def test_create_minimal_envelope(self):
        """Test creating envelope with minimal fields."""
        envelope = ContextEnvelope()
        assert envelope.tenant_id is None
        assert envelope.principal_id is None
        assert envelope.attributes == {}

    def test_create_full_envelope(self):
        """Test creating envelope with all fields."""
        envelope = ContextEnvelope(
            tenant_id="tenant-1",
            principal_id="user-123",
            session_id="sess-456",
            request_id="req-789",
            agent_id="agent-1",
            attributes={"role": "admin", "department": "engineering"},
        )
        assert envelope.tenant_id == "tenant-1"
        assert envelope.principal_id == "user-123"
        assert envelope.session_id == "sess-456"
        assert envelope.request_id == "req-789"
        assert envelope.agent_id == "agent-1"
        assert envelope.attributes["role"] == "admin"

    def test_attribute_types(self):
        """Test valid attribute types."""
        envelope = ContextEnvelope(
            attributes={
                "string_val": "hello",
                "int_val": 42,
                "float_val": 3.14,
                "bool_val": True,
            }
        )
        assert envelope.attributes["string_val"] == "hello"
        assert envelope.attributes["int_val"] == 42
        assert envelope.attributes["float_val"] == 3.14
        assert envelope.attributes["bool_val"] is True

    def test_timestamp_auto_generated(self):
        """Test timestamp is auto-generated."""
        envelope = ContextEnvelope()
        assert envelope.timestamp is not None

    def test_custom_timestamp(self):
        """Test custom timestamp."""
        from datetime import datetime, timezone

        ts = datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        envelope = ContextEnvelope(timestamp=ts)
        assert envelope.timestamp == ts
