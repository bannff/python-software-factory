"""Configuration management for UI module."""

import logging
import os
from pathlib import Path
from typing import Any

import yaml

from .config_models import UISettings, ViewDefinition
from .config_schema import get_config_schema

logger = logging.getLogger(__name__)

# Re-export for backwards compatibility
__all__ = ["UISettings", "ViewDefinition", "ConfigLoader", "get_config_schema"]


class ConfigLoader:
    """Loads configuration from config_dir."""

    def __init__(self, config_dir: str | Path | None = None):
        self.config_dir = Path(config_dir) if config_dir else self._default_config_dir()
        self._settings: UISettings | None = None
        self._view_definitions: dict[str, ViewDefinition] = {}

    def _default_config_dir(self) -> Path:
        env_dir = os.environ.get("UI_CONFIG_DIR")
        return Path(env_dir) if env_dir else Path("./config")

    def _validate_path(self, path: Path) -> None:
        try:
            resolved = path.resolve()
            config_resolved = self.config_dir.resolve()
        except Exception as e:
            raise ValueError(f"Invalid path: {path}") from e
        if not str(resolved).startswith(str(config_resolved)):
            raise ValueError(f"Path traversal detected: {path}")

    def load_settings(self) -> UISettings:
        if self._settings:
            return self._settings

        settings_path = self.config_dir / "settings.yaml"
        if not settings_path.exists():
            logger.info(f"No settings.yaml found at {settings_path}, using defaults")
            self._settings = UISettings()
            return self._settings

        self._validate_path(settings_path)
        with open(settings_path) as f:
            data = yaml.safe_load(f) or {}

        if os.environ.get("AUTHORING_ENABLED", "").lower() == "true":
            data["authoring_enabled"] = True

        self._settings = UISettings.from_dict(data)
        logger.info(f"Loaded settings from {settings_path}")
        return self._settings

    def load_view_definitions(self) -> dict[str, ViewDefinition]:
        if self._view_definitions:
            return self._view_definitions

        views_dir = self.config_dir / "views"
        if not views_dir.exists():
            logger.info(f"No views directory at {views_dir}")
            return {}

        self._validate_path(views_dir)
        for yaml_file in views_dir.glob("*.yaml"):
            self._validate_path(yaml_file)
            try:
                with open(yaml_file) as f:
                    data = yaml.safe_load(f) or {}
                view_id = data.get("id", yaml_file.stem)
                definition = ViewDefinition(
                    id=view_id, name=data.get("name", view_id),
                    description=data.get("description", ""),
                    layout=data.get("layout", {}),
                    components=data.get("components", []),
                    metadata=data.get("metadata", {}),
                    tags=data.get("tags", []),
                )
                self._view_definitions[view_id] = definition
                logger.debug(f"Loaded view definition: {view_id}")
            except Exception as e:
                logger.error(f"Failed to load view from {yaml_file}: {e}")

        logger.info(f"Loaded {len(self._view_definitions)} view definitions")
        return self._view_definitions

    def reload(self) -> None:
        self._settings = None
        self._view_definitions = {}
        self.load_settings()
        self.load_view_definitions()

    def get_config_schema(self) -> dict[str, Any]:
        return get_config_schema()
