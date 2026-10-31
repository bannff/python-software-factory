"""Tests for channel registry."""
from __future__ import annotations

import pytest
from pathlib import Path

from factory.notification.runtime.channels import ChannelRegistry


def _create_channel_config(tmp_path: Path) -> Path:
    """Create test channel config."""
    cfg = tmp_path / "config"
    channels_dir = cfg / "channels"
    channels_dir.mkdir(parents=True)
    
    (channels_dir / "console.yaml").write_text("""
id: console
type: console
enabled: true
config:
  prefix: "[NOTIFY]"
""")
    
    (channels_dir / "slack.yaml").write_text("""
id: slack-alerts
type: slack
enabled: true
config:
  webhook_url: "https://hooks.slack.com/xxx"
  channel: "#alerts"
""")
    
    (channels_dir / "email.yaml").write_text("""
id: email-main
type: email
enabled: false
config:
  smtp_host: "smtp.example.com"
  smtp_port: 587
""")
    
    return cfg


class TestChannelRegistry:
    """Test channel registry loading."""

    def test_loads_channels_from_config(self, tmp_path: Path) -> None:
        """Should load channels from config/channels/*.yaml."""
        cfg = _create_channel_config(tmp_path)
        registry = ChannelRegistry(cfg)
        
        channels = registry.as_list()
        assert len(channels) == 3
        
        ids = [c["id"] for c in channels]
        assert "console" in ids
        assert "slack-alerts" in ids
        assert "email-main" in ids

    def test_get_channel_by_id(self, tmp_path: Path) -> None:
        """Should retrieve channel by ID."""
        cfg = _create_channel_config(tmp_path)
        registry = ChannelRegistry(cfg)
        
        channel = registry.get("slack-alerts")
        assert channel is not None
        assert channel.type == "slack"
        assert channel.enabled is True

    def test_get_enabled_channels(self, tmp_path: Path) -> None:
        """Should filter to enabled channels only."""
        cfg = _create_channel_config(tmp_path)
        registry = ChannelRegistry(cfg)
        
        enabled = registry.get_enabled()
        assert len(enabled) == 2  # console and slack, not email
        
        ids = [c.id for c in enabled]
        assert "email-main" not in ids

    def test_sanitized_list_hides_secrets(self, tmp_path: Path) -> None:
        """Should not expose sensitive config in as_list."""
        cfg = _create_channel_config(tmp_path)
        registry = ChannelRegistry(cfg)
        
        channels = registry.as_list()
        slack = next(c for c in channels if c["id"] == "slack-alerts")
        
        # webhook_url should be redacted
        assert "webhook_url" not in slack.get("config", {})
        # But type and enabled should be visible
        assert slack["type"] == "slack"
        assert slack["enabled"] is True
