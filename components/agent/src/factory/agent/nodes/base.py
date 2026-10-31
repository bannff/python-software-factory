"""
Base class for custom graph nodes.
"""

from abc import ABC, abstractmethod
from typing import Any


class CustomNode(ABC):
    """
    Base class for custom graph nodes.

    Implement this to create deterministic business logic nodes
    that can be used in graphs alongside agents and swarms.

    Example:
        class ValidationNode(CustomNode):
            def __init__(self, min_confidence: float = 0.8):
                self.min_confidence = min_confidence

            async def invoke_async(self, task, invocation_state=None, **kwargs):
                data = invocation_state.get("data", {})
                is_valid = data.get("confidence", 0) >= self.min_confidence
                return {"valid": is_valid, "data": data}
    """

    @abstractmethod
    async def invoke_async(
        self, task: Any, invocation_state: dict[str, Any] | None = None, **kwargs: Any
    ) -> dict[str, Any]:
        """
        Execute the node logic.

        Args:
            task: The input task/data
            invocation_state: Context passed through the graph
            **kwargs: Additional arguments

        Returns:
            Result dictionary
        """
        pass

    def __call__(self, task: Any, **kwargs: Any) -> Any:
        """Synchronous call (wraps async)."""
        import asyncio

        return asyncio.run(self.invoke_async(task, **kwargs))


class ValidationNode(CustomNode):
    """
    Example validation node for deterministic checks.

    Validates that required fields are present and confidence meets threshold.
    """

    def __init__(
        self,
        required_fields: list[str] | None = None,
        min_confidence: float = 0.0,
    ):
        self.required_fields = required_fields or []
        self.min_confidence = min_confidence

    async def invoke_async(
        self, task: Any, invocation_state: dict[str, Any] | None = None, **kwargs: Any
    ) -> dict[str, Any]:
        """Validate the input data."""
        state = invocation_state or {}
        data = state.get("data", {})

        # Check required fields
        missing_fields = [f for f in self.required_fields if f not in data]

        # Check confidence
        confidence = data.get("confidence", 1.0)
        confidence_ok = confidence >= self.min_confidence

        is_valid = len(missing_fields) == 0 and confidence_ok

        return {
            "valid": is_valid,
            "passed": is_valid,
            "missing_fields": missing_fields,
            "confidence": confidence,
            "confidence_ok": confidence_ok,
            "data": data,
        }


class TransformNode(CustomNode):
    """
    Example transform node for data transformation.

    Applies a transformation function to the input data.
    """

    def __init__(self, transform_fn: Any = None):
        self.transform_fn = transform_fn or (lambda x: x)

    async def invoke_async(
        self, task: Any, invocation_state: dict[str, Any] | None = None, **kwargs: Any
    ) -> dict[str, Any]:
        """Transform the input data."""
        state = invocation_state or {}
        data = state.get("data", task)

        try:
            result = self.transform_fn(data)
            return {
                "success": True,
                "data": result,
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "data": data,
            }
