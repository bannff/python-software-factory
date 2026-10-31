"""Blueprint runtime - runtime and adapters."""

from .runtime import BlueprintRuntime

__all__ = ["BlueprintRuntime"]


_runtime: BlueprintRuntime | None = None


def get_runtime() -> BlueprintRuntime:
    """Get the global blueprint runtime."""
    global _runtime
    if _runtime is None:
        _runtime = BlueprintRuntime()
    return _runtime


def reset_runtime() -> None:
    """Reset the global runtime (for testing)."""
    global _runtime
    _runtime = None
