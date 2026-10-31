"""Tests for custom node implementations - Validation and Transform nodes.

See also:
- test_nodes_swarm.py - SwarmNode tests
"""

import pytest

from factory.agent.nodes.base import CustomNode, ValidationNode, TransformNode


class TestValidationNode:
    """Tests for ValidationNode."""

    @pytest.mark.asyncio
    async def test_validation_passes(self):
        """Test validation passes with all required fields."""
        node = ValidationNode(
            required_fields=["name", "email"],
            min_confidence=0.8,
        )

        result = await node.invoke_async(
            "validate",
            invocation_state={
                "data": {
                    "name": "Alice",
                    "email": "alice@example.com",
                    "confidence": 0.9,
                }
            },
        )

        assert result["valid"] is True
        assert result["passed"] is True
        assert result["missing_fields"] == []
        assert result["confidence_ok"] is True

    @pytest.mark.asyncio
    async def test_validation_fails_missing_fields(self):
        """Test validation fails with missing required fields."""
        node = ValidationNode(required_fields=["name", "email", "phone"])

        result = await node.invoke_async(
            "validate",
            invocation_state={"data": {"name": "Bob"}},
        )

        assert result["valid"] is False
        assert "email" in result["missing_fields"]
        assert "phone" in result["missing_fields"]

    @pytest.mark.asyncio
    async def test_validation_fails_low_confidence(self):
        """Test validation fails with low confidence."""
        node = ValidationNode(min_confidence=0.9)

        result = await node.invoke_async(
            "validate",
            invocation_state={"data": {"confidence": 0.5}},
        )

        assert result["valid"] is False
        assert result["confidence_ok"] is False

    @pytest.mark.asyncio
    async def test_validation_empty_state(self):
        """Test validation with empty invocation state."""
        node = ValidationNode()

        result = await node.invoke_async("validate", invocation_state=None)

        assert result["valid"] is True  # No requirements
        assert result["data"] == {}


class TestTransformNode:
    """Tests for TransformNode."""

    @pytest.mark.asyncio
    async def test_transform_success(self):
        """Test successful transformation."""
        node = TransformNode(transform_fn=lambda x: x.upper())

        result = await node.invoke_async(
            "transform", invocation_state={"data": "hello"}
        )

        assert result["success"] is True
        assert result["data"] == "HELLO"

    @pytest.mark.asyncio
    async def test_transform_with_dict(self):
        """Test transformation with dictionary data."""

        def add_timestamp(data):
            return {**data, "processed": True}

        node = TransformNode(transform_fn=add_timestamp)

        result = await node.invoke_async(
            "transform", invocation_state={"data": {"name": "test"}}
        )

        assert result["success"] is True
        assert result["data"]["name"] == "test"
        assert result["data"]["processed"] is True

    @pytest.mark.asyncio
    async def test_transform_error(self):
        """Test transformation error handling."""

        def bad_transform(x):
            raise ValueError("Transform failed")

        node = TransformNode(transform_fn=bad_transform)

        result = await node.invoke_async(
            "transform", invocation_state={"data": "test"}
        )

        assert result["success"] is False
        assert "Transform failed" in result["error"]

    @pytest.mark.asyncio
    async def test_transform_identity(self):
        """Test default identity transformation."""
        node = TransformNode()  # No transform_fn

        result = await node.invoke_async(
            "transform", invocation_state={"data": {"key": "value"}}
        )

        assert result["success"] is True
        assert result["data"] == {"key": "value"}


class TestCustomNodeInterface:
    """Tests for CustomNode abstract interface."""

    def test_cannot_instantiate_abstract(self):
        """Test that CustomNode cannot be instantiated directly."""
        with pytest.raises(TypeError):
            CustomNode()

    def test_subclass_must_implement_invoke_async(self):
        """Test that subclasses must implement invoke_async."""

        class IncompleteNode(CustomNode):
            pass

        with pytest.raises(TypeError):
            IncompleteNode()

    @pytest.mark.asyncio
    async def test_valid_subclass(self):
        """Test that valid subclasses work correctly."""

        class SimpleNode(CustomNode):
            async def invoke_async(self, task, invocation_state=None, **kwargs):
                return {"task": str(task), "processed": True}

        node = SimpleNode()
        result = await node.invoke_async("test task")

        assert result["task"] == "test task"
        assert result["processed"] is True
