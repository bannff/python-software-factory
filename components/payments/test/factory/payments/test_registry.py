"""Tests for provider registry."""

import pytest
from factory.payments.runtime.registry import (
    ProviderConfig,
    ProviderRegistry,
    ProviderStats,
    ProviderType,
)


class TestProviderConfig:
    """Tests for ProviderConfig model."""

    def test_create_mock_config(self):
        """Test creating a mock provider config."""
        config = ProviderConfig(
            name="test-mock",
            provider_type=ProviderType.MOCK,
        )
        assert config.name == "test-mock"
        assert config.provider_type == ProviderType.MOCK
        assert config.enabled is True

    def test_create_stripe_config(self):
        """Test creating a Stripe provider config."""
        config = ProviderConfig(
            name="stripe-prod",
            provider_type=ProviderType.STRIPE,
            api_key="sk_test_xxx",
            options={"webhook_secret": "whsec_xxx"},
        )
        assert config.provider_type == ProviderType.STRIPE
        assert config.api_key == "sk_test_xxx"

    def test_disabled_config(self):
        """Test creating a disabled provider config."""
        config = ProviderConfig(
            name="disabled-provider",
            provider_type=ProviderType.MOCK,
            enabled=False,
        )
        assert config.enabled is False


class TestProviderStats:
    """Tests for ProviderStats model."""

    def test_create_stats(self):
        """Test creating provider stats."""
        stats = ProviderStats(
            name="stripe-prod",
            provider_type=ProviderType.STRIPE,
            connected=True,
            transaction_count=100,
            total_amount_cents=500000,
        )
        assert stats.connected is True
        assert stats.transaction_count == 100
        assert stats.total_amount_cents == 500000

    def test_disconnected_stats(self):
        """Test stats for disconnected provider."""
        stats = ProviderStats(
            name="stripe-prod",
            provider_type=ProviderType.STRIPE,
            connected=False,
            error="API key invalid",
        )
        assert stats.connected is False
        assert stats.error == "API key invalid"


class TestProviderRegistry:
    """Tests for ProviderRegistry."""

    def test_register_provider(self):
        """Test registering a provider."""
        registry = ProviderRegistry()
        config = ProviderConfig(
            name="test-provider",
            provider_type=ProviderType.MOCK,
        )
        registry.register(config)
        assert "test-provider" in registry.list_providers()

    def test_unregister_provider(self):
        """Test unregistering a provider."""
        registry = ProviderRegistry()
        config = ProviderConfig(
            name="test-provider",
            provider_type=ProviderType.MOCK,
        )
        registry.register(config)
        registry.unregister("test-provider")
        assert "test-provider" not in registry.list_providers()

    def test_get_provider(self):
        """Test getting a provider by name."""
        registry = ProviderRegistry()
        config = ProviderConfig(
            name="test-provider",
            provider_type=ProviderType.MOCK,
        )
        registry.register(config)
        retrieved = registry.get("test-provider")
        assert retrieved is not None
        assert retrieved.name == "test-provider"

    def test_get_nonexistent_provider(self):
        """Test getting a non-existent provider."""
        registry = ProviderRegistry()
        assert registry.get("nonexistent") is None

    def test_list_by_type(self):
        """Test listing providers by type."""
        registry = ProviderRegistry()
        registry.register(ProviderConfig(
            name="mock1", provider_type=ProviderType.MOCK
        ))
        registry.register(ProviderConfig(
            name="mock2", provider_type=ProviderType.MOCK
        ))
        registry.register(ProviderConfig(
            name="stripe1", provider_type=ProviderType.STRIPE, api_key="sk_test"
        ))
        
        mock_providers = registry.list_by_type(ProviderType.MOCK)
        assert len(mock_providers) == 2
        assert "mock1" in mock_providers
        assert "mock2" in mock_providers

    def test_get_stats(self):
        """Test getting provider stats."""
        registry = ProviderRegistry()
        config = ProviderConfig(
            name="test-provider",
            provider_type=ProviderType.MOCK,
        )
        registry.register(config)
        stats = registry.get_stats("test-provider")
        assert stats is not None
        assert stats.name == "test-provider"

    def test_duplicate_registration_raises(self):
        """Test that duplicate registration raises error."""
        registry = ProviderRegistry()
        config = ProviderConfig(
            name="test-provider",
            provider_type=ProviderType.MOCK,
        )
        registry.register(config)
        with pytest.raises(ValueError, match="already registered"):
            registry.register(config)

    def test_record_transaction(self):
        """Test recording a transaction."""
        registry = ProviderRegistry()
        registry.register(ProviderConfig(
            name="test-provider", provider_type=ProviderType.MOCK
        ))
        registry.record_transaction("test-provider", "tx123", 5000)
        stats = registry.get_stats("test-provider")
        assert stats.transaction_count == 1
        assert stats.total_amount_cents == 5000

    def test_to_dict(self):
        """Test converting registry to dict."""
        registry = ProviderRegistry()
        registry.register(ProviderConfig(
            name="provider1", provider_type=ProviderType.MOCK
        ))
        result = registry.to_dict()
        assert "providers" in result
        assert len(result["providers"]) == 1
