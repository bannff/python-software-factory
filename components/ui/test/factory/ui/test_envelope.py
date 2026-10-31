"""Tests for context envelope."""

import pytest

from factory.ui.runtime import ContextEnvelope
from factory.ui.runtime.envelope import (
    MAX_ATTRIBUTE_KEY_LENGTH,
    MAX_ATTRIBUTE_VALUE_LENGTH,
    MAX_ATTRIBUTES,
)


class TestContextEnvelope:
    """Tests for ContextEnvelope."""

    def test_default_values(self):
        """Should have sensible defaults."""
        envelope = ContextEnvelope()

        assert envelope.tenant_id is None
        assert envelope.request_id is not None  # Auto-generated
        assert envelope.attributes == {}

    def test_from_dict(self):
        """Should create from dictionary."""
        data = {
            "tenant_id": "acme",
            "principal_id": "user-123",
            "correlation_id": "trace-456",
        }
        envelope = ContextEnvelope.from_dict(data)

        assert envelope.tenant_id == "acme"
        assert envelope.principal_id == "user-123"
        assert envelope.correlation_id == "trace-456"

    def test_from_dict_none(self):
        """Should handle None gracefully."""
        envelope = ContextEnvelope.from_dict(None)
        assert envelope.request_id is not None

    def test_to_dict(self):
        """Should convert to dictionary."""
        envelope = ContextEnvelope(
            tenant_id="acme",
            agent_id="test-agent",
        )
        data = envelope.to_dict()

        assert data["tenant_id"] == "acme"
        assert data["agent_id"] == "test-agent"
        assert "timestamp" in data

    def test_with_tool(self):
        """Should create copy with tool_name."""
        envelope = ContextEnvelope(tenant_id="acme")
        with_tool = envelope.with_tool("ui_add_component")

        assert with_tool.tool_name == "ui_add_component"
        assert with_tool.tenant_id == "acme"
        assert envelope.tool_name is None  # Original unchanged

    def test_attribute_validation_count(self):
        """Should reject too many attributes."""
        attrs = {f"key_{i}": f"value_{i}" for i in range(MAX_ATTRIBUTES + 1)}

        with pytest.raises(ValueError, match="Too many attributes"):
            ContextEnvelope(attributes=attrs)

    def test_attribute_validation_key_length(self):
        """Should reject long attribute keys."""
        long_key = "x" * (MAX_ATTRIBUTE_KEY_LENGTH + 1)

        with pytest.raises(ValueError, match="Attribute key too long"):
            ContextEnvelope(attributes={long_key: "value"})

    def test_attribute_validation_value_length(self):
        """Should reject long attribute values."""
        long_value = "x" * (MAX_ATTRIBUTE_VALUE_LENGTH + 1)

        with pytest.raises(ValueError, match="Attribute value too long"):
            ContextEnvelope(attributes={"key": long_value})

    def test_attribute_validation_type(self):
        """Should reject invalid attribute types."""
        with pytest.raises(ValueError, match="Invalid attribute type"):
            ContextEnvelope(attributes={"key": [1, 2, 3]})  # list not allowed

    def test_valid_attribute_types(self):
        """Should accept valid attribute types."""
        envelope = ContextEnvelope(
            attributes={
                "string": "value",
                "int": 42,
                "float": 3.14,
                "bool": True,
            }
        )

        assert envelope.attributes["string"] == "value"
        assert envelope.attributes["int"] == 42
        assert envelope.attributes["float"] == 3.14
        assert envelope.attributes["bool"] is True
