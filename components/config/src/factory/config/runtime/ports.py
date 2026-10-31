"""Abstract ports for config brick.

Ports define what capabilities the config brick needs, not how they're implemented.
Adapters plug in specific backends (env vars, files, AWS SSM, etc.)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol


@dataclass
class ConfigHealth:
    """Health status for a config backend."""
    healthy: bool
    backend: str
    latency_ms: float = 0.0
    message: str = ""
    details: dict[str, Any] = field(default_factory=dict)


@dataclass
class ConfigValue:
    """A configuration value with metadata."""
    key: str
    value: Any
    source: str = "unknown"  # Which backend provided this value
    is_secret: bool = False  # Whether this is a secret reference
    environment: str | None = None  # Environment this applies to


class ConfigStore(Protocol):
    """Port: Configuration storage backend."""

    def get(self, key: str, default: Any = None) -> Any:
        """Get a configuration value."""
        ...

    def get_typed(self, key: str, value_type: type, default: Any = None) -> Any:
        """Get a configuration value with type coercion."""
        ...

    def set(self, key: str, value: Any) -> bool:
        """Set a configuration value. Returns True on success."""
        ...

    def delete(self, key: str) -> bool:
        """Delete a configuration key. Returns True if key existed."""
        ...

    def exists(self, key: str) -> bool:
        """Check if a configuration key exists."""
        ...

    def keys(self, prefix: str = "") -> list[str]:
        """List configuration keys with optional prefix filter."""
        ...

    def get_all(self, prefix: str = "") -> dict[str, Any]:
        """Get all configuration values with optional prefix filter."""
        ...

    def health_check(self) -> ConfigHealth:
        """Check config store health."""
        ...


class FeatureFlagStore(Protocol):
    """Port: Feature flag evaluation."""

    def is_enabled(self, flag: str, context: dict[str, Any] | None = None) -> bool:
        """Check if a feature flag is enabled."""
        ...

    def get_variant(self, flag: str, context: dict[str, Any] | None = None) -> str | None:
        """Get the variant for a feature flag (for A/B testing)."""
        ...

    def list_flags(self) -> list[str]:
        """List all feature flags."""
        ...
