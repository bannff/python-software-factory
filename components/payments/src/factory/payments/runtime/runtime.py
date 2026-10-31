import yaml
from pathlib import Path
from typing import Dict, Any, Optional

from .ports import PaymentGateway
from .providers.mock_provider import MockProvider


class Runtime:
    """
    Orchestrator for the Payments Module.
    Loads configuration and initializes the active provider.
    """

    def __init__(self, config_dir: Path, settings: Optional[Dict[str, Any]] = None):
        self.config_dir = config_dir
        self.settings = settings if settings is not None else self._load_settings()
        self.provider = self._init_provider()

    def _load_settings(self) -> Dict[str, Any]:
        settings_path = self.config_dir / "settings.yaml"
        if not settings_path.exists():
            return {}
        with open(settings_path, "r") as f:
            return yaml.safe_load(f) or {}

    def _init_provider(self) -> PaymentGateway:
        provider_name = self.settings.get("provider", "mock")
        if provider_name == "stripe":
            from .providers.stripe_provider import StripeProvider, StripeConfig

            api_key = self.settings.get("stripe_api_key", "")
            webhook_secret = self.settings.get("stripe_webhook_secret")
            api_version = self.settings.get("stripe_api_version")
            config = StripeConfig(
                api_key=api_key,
                webhook_secret=webhook_secret,
                api_version=api_version,
            )
            return StripeProvider(config)
        return MockProvider()

    @property
    def active_provider(self) -> PaymentGateway:
        return self.provider

    @staticmethod
    def available_providers() -> list[str]:
        """List available provider backends."""
        return ["mock", "stripe"]
