"""Channel registry for loading and managing notification channels."""
from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from factory.notification.runtime.config import ChannelConfig


class ChannelRegistry:
    """Registry for notification channels loaded from config."""

    def __init__(self, config_dir: Path):
        self.config_dir = Path(config_dir)
        self.channels: dict[str, ChannelConfig] = {}
        self._load_channels()

    def _load_channels(self) -> None:
        """Load channels from config/channels/*.yaml."""
        channels_dir = self.config_dir / "channels"
        if not channels_dir.exists():
            return

        for path in channels_dir.glob("*.yaml"):
            try:
                data = yaml.safe_load(path.read_text())
                if data:
                    channel = ChannelConfig.model_validate(data)
                    self.channels[channel.id] = channel
            except Exception:
                # Skip invalid files
                pass

    def get(self, channel_id: str) -> ChannelConfig | None:
        """Get channel by ID."""
        return self.channels.get(channel_id)

    def get_enabled(self) -> list[ChannelConfig]:
        """Get all enabled channels."""
        return [c for c in self.channels.values() if c.enabled]

    def as_list(self) -> list[dict[str, Any]]:
        """Return sanitized list of channels (no secrets)."""
        return [c.sanitized() for c in self.channels.values()]
