"""Common storage models."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class StorageHealth:
    """Health status for a storage backend."""
    healthy: bool
    backend: str
    latency_ms: float = 0.0
    message: str = ""
    details: dict[str, Any] = field(default_factory=dict)
