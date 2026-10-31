"""Tests for config validation."""
from __future__ import annotations

import pytest
from pydantic import ValidationError

from factory.notification.runtime.config import (
    Settings,
    ChannelConfig,
    TemplateConfig,
    SCHEMA_VERSION,
)


class TestSettings:
    """Test settings validation."""

    def test_valid_settings(self) -> None:
        """Should accept valid settings."""
        settings = Settings(
            service={"name": "test-service", "version": "1.0.0"},
            default_channel="console",
        )
        assert settings.service.name == "test-service"
        assert settings.default_channel == "console"

    def test_default_values(self) -> None:
        """Should have sensible defaults."""
        settings = Settings(service={"name": "test"})
        assert settings.authoring.enabled is False
        assert settings.schema_version == SCHEMA_VERSION

    def test_service_name_required(self) -> None:
        """Should require service name."""
        with pytest.raises(ValidationError):
            Settings(service={})


class TestChannelConfig:
    """Test channel config validation."""

    def test_valid_channel(self) -> None:
        """Should accept valid channel config."""
        channel = ChannelConfig(
            id="slack-main",
            type="slack",
            config={"webhook_url": "https://hooks.slack.com/xxx"},
        )
        assert channel.id == "slack-main"
        assert channel.type == "slack"
        assert channel.enabled is True  # default

    def test_id_required(self) -> None:
        """Should require channel ID."""
        with pytest.raises(ValidationError):
            ChannelConfig(type="slack", config={})


class TestTemplateConfig:
    """Test template config validation."""

    def test_valid_template(self) -> None:
        """Should accept valid template config."""
        template = TemplateConfig(
            id="welcome",
            name="Welcome Email",
            subject="Welcome {{name}}",
            body="Hello {{name}}, welcome!",
            variables=["name"],
        )
        assert template.id == "welcome"
        assert "name" in template.variables

    def test_body_required(self) -> None:
        """Should require body."""
        with pytest.raises(ValidationError):
            TemplateConfig(
                id="test",
                name="Test",
                subject="Test",
                variables=[],
            )
