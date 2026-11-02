"""Typed failure for the chat-model catalog."""
from __future__ import annotations


class CatalogUnavailable(ValueError):
    """The catalog cannot be built; ``reason`` is a safe, stable code.

    ``not_configured``: no chat model selector and no allowed profile exist, so
    there is nothing to list (the normal state of a fresh install).
    ``malformed``: a configured selector failed to resolve.
    """

    def __init__(self, reason: str) -> None:
        super().__init__("chat model catalog unavailable")
        self.reason = reason


__all__ = ["CatalogUnavailable"]
