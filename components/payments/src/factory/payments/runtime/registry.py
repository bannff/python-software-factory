"""Provider registry for managing payment gateways."""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class ProviderType(str, Enum):
    """Types of payment providers."""
    MOCK = "mock"
    STRIPE = "stripe"
    PAYPAL = "paypal"


class ProviderConfig(BaseModel):
    """Configuration for a payment provider."""
    name: str = Field(..., description="Unique provider name")
    provider_type: ProviderType = Field(..., description="Type of provider")
    api_key: str | None = Field(None, description="API key (secret)")
    public_key: str | None = Field(None, description="Public/publishable key")
    enabled: bool = Field(True, description="Whether provider is enabled")
    sandbox: bool = Field(True, description="Use sandbox/test mode")
    options: dict[str, Any] = Field(default_factory=dict, description="Additional options")


class ProviderStats(BaseModel):
    """Statistics for a payment provider."""
    name: str
    provider_type: ProviderType
    connected: bool = True
    transaction_count: int = 0
    total_amount_cents: int = 0
    refund_count: int = 0
    total_refund_cents: int = 0
    last_transaction_at: str | None = None
    error: str | None = None
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class ProviderRegistry:
    """Registry for managing payment providers."""

    def __init__(self) -> None:
        self._providers: dict[str, ProviderConfig] = {}
        self._stats: dict[str, ProviderStats] = {}

    def register(self, config: ProviderConfig) -> None:
        """Register a provider."""
        if config.name in self._providers:
            raise ValueError(f"Provider '{config.name}' already registered")
        self._providers[config.name] = config
        self._stats[config.name] = ProviderStats(
            name=config.name,
            provider_type=config.provider_type,
        )

    def unregister(self, name: str) -> None:
        """Unregister a provider."""
        self._providers.pop(name, None)
        self._stats.pop(name, None)

    def get(self, name: str) -> ProviderConfig | None:
        """Get a provider by name."""
        return self._providers.get(name)

    def list_providers(self) -> list[str]:
        """List all provider names."""
        return list(self._providers.keys())

    def list_by_type(self, provider_type: ProviderType) -> list[str]:
        """List providers by type."""
        return [
            name for name, config in self._providers.items()
            if config.provider_type == provider_type
        ]

    def get_stats(self, name: str) -> ProviderStats | None:
        """Get stats for a provider."""
        return self._stats.get(name)

    def record_transaction(self, name: str, tx_id: str, amount_cents: int) -> None:
        """Record a transaction for a provider."""
        if name in self._stats:
            self._stats[name].transaction_count += 1
            self._stats[name].total_amount_cents += amount_cents
            self._stats[name].last_transaction_at = datetime.now(timezone.utc).isoformat()

    def record_refund(self, name: str, amount_cents: int) -> None:
        """Record a refund for a provider."""
        if name in self._stats:
            self._stats[name].refund_count += 1
            self._stats[name].total_refund_cents += amount_cents

    def update_connection_status(self, name: str, connected: bool, error: str | None = None) -> None:
        """Update connection status for a provider."""
        if name in self._stats:
            self._stats[name].connected = connected
            self._stats[name].error = error

    def to_dict(self) -> dict[str, Any]:
        """Convert registry to dict (redacting secrets)."""
        return {
            "providers": [
                {
                    "name": config.name,
                    "type": config.provider_type.value,
                    "enabled": config.enabled,
                    "sandbox": config.sandbox,
                    "connected": self._stats[config.name].connected if config.name in self._stats else False,
                    "transaction_count": self._stats[config.name].transaction_count if config.name in self._stats else 0,
                    "total_amount_cents": self._stats[config.name].total_amount_cents if config.name in self._stats else 0,
                }
                for config in self._providers.values()
            ]
        }


# Global registry instance
_registry: ProviderRegistry | None = None


def get_registry() -> ProviderRegistry:
    """Get the global provider registry."""
    global _registry
    if _registry is None:
        _registry = ProviderRegistry()
    return _registry


def reset_registry() -> None:
    """Reset the global registry (for testing)."""
    global _registry
    _registry = None
