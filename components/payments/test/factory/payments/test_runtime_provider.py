"""Tests for payments Runtime provider selection.

Verifies that Runtime correctly routes to MockProvider or StripeProvider
based on settings configuration.
"""

from __future__ import annotations

import pytest
from unittest.mock import patch, MagicMock

from factory.payments.runtime.runtime import Runtime
from factory.payments.runtime.providers.mock_provider import MockProvider


class TestRuntimeProviderSelection:
    """Tests for Runtime._init_provider() routing."""

    def test_default_is_mock(self, tmp_path) -> None:
        """Default provider (no settings) is MockProvider."""
        (tmp_path / "settings.yaml").write_text("")
        runtime = Runtime(config_dir=tmp_path)
        assert isinstance(runtime.provider, MockProvider)
        assert runtime.active_provider.provider_id == "mock"

    def test_explicit_mock(self, tmp_path) -> None:
        """Explicit provider=mock selects MockProvider."""
        runtime = Runtime(config_dir=tmp_path, settings={"provider": "mock"})
        assert isinstance(runtime.provider, MockProvider)

    def test_stripe_selection(self, tmp_path) -> None:
        """provider=stripe instantiates StripeProvider."""
        from factory.payments.runtime.providers.stripe_provider import StripeProvider

        runtime = Runtime(
            config_dir=tmp_path,
            settings={
                "provider": "stripe",
                "stripe_api_key": "sk_test_fake",
                "stripe_webhook_secret": "whsec_fake",
            },
        )
        assert isinstance(runtime.provider, StripeProvider)

    def test_stripe_config_passthrough(self, tmp_path) -> None:
        """Stripe config values are passed to StripeConfig."""
        from factory.payments.runtime.providers.stripe_provider import StripeProvider

        runtime = Runtime(
            config_dir=tmp_path,
            settings={
                "provider": "stripe",
                "stripe_api_key": "sk_test_key123",
                "stripe_webhook_secret": "whsec_secret456",
                "stripe_api_version": "2024-01-01",
            },
        )
        provider = runtime.provider
        assert isinstance(provider, StripeProvider)
        assert provider._config.api_key == "sk_test_key123"
        assert provider._config.webhook_secret == "whsec_secret456"
        assert provider._config.api_version == "2024-01-01"

    def test_available_providers(self) -> None:
        """available_providers lists mock and stripe."""
        providers = Runtime.available_providers()
        assert "mock" in providers
        assert "stripe" in providers

    def test_settings_from_yaml(self, tmp_path) -> None:
        """Runtime loads settings from settings.yaml when not passed."""
        import yaml
        settings_file = tmp_path / "settings.yaml"
        settings_file.write_text(yaml.dump({"provider": "mock"}))
        runtime = Runtime(config_dir=tmp_path)
        assert isinstance(runtime.provider, MockProvider)

    def test_settings_override_yaml(self, tmp_path) -> None:
        """Explicit settings dict overrides settings.yaml."""
        import yaml
        settings_file = tmp_path / "settings.yaml"
        settings_file.write_text(yaml.dump({"provider": "mock"}))
        runtime = Runtime(
            config_dir=tmp_path,
            settings={"provider": "stripe", "stripe_api_key": "sk_test_x"},
        )
        from factory.payments.runtime.providers.stripe_provider import StripeProvider
        assert isinstance(runtime.provider, StripeProvider)
