"""Tests for ConfigLoader."""

import tempfile
from pathlib import Path

import pytest

from factory.ui.runtime import ConfigLoader


class TestConfigLoader:
    """Tests for ConfigLoader."""

    def test_default_settings(self):
        """Should return default settings when no config file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            loader = ConfigLoader(tmpdir)
            settings = loader.load_settings()

            assert settings.authoring_enabled is False
            assert settings.storage_backend == "memory"
            assert settings.default_adapter == "json"

    def test_load_settings_from_file(self):
        """Should load settings from yaml file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create settings file
            settings_path = Path(tmpdir) / "settings.yaml"
            settings_path.write_text("""
authoring_enabled: true
storage_backend: redis
max_views: 500
""")

            loader = ConfigLoader(tmpdir)
            settings = loader.load_settings()

            assert settings.authoring_enabled is True
            assert settings.storage_backend == "redis"
            assert settings.max_views == 500

    def test_load_view_definitions(self):
        """Should load view definitions from views directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create views directory
            views_dir = Path(tmpdir) / "views"
            views_dir.mkdir()

            # Create view file
            (views_dir / "dashboard.yaml").write_text("""
id: test-dashboard
name: Test Dashboard
layout:
  type: grid
  columns: 2
components:
  - type: text
    props:
      content: Hello
tags:
  - test
""")

            loader = ConfigLoader(tmpdir)
            definitions = loader.load_view_definitions()

            assert "test-dashboard" in definitions
            assert definitions["test-dashboard"].name == "Test Dashboard"
            assert len(definitions["test-dashboard"].components) == 1

    def test_view_definition_to_view(self):
        """Should convert ViewDefinition to UIView."""
        with tempfile.TemporaryDirectory() as tmpdir:
            views_dir = Path(tmpdir) / "views"
            views_dir.mkdir()

            (views_dir / "test.yaml").write_text("""
id: test-view
name: Test View
components:
  - id: comp-1
    type: metric
    props:
      label: Users
      value: 100
""")

            loader = ConfigLoader(tmpdir)
            definitions = loader.load_view_definitions()

            view = definitions["test-view"].to_view()

            assert view.id == "test-view"
            assert view.name == "Test View"
            assert len(view.components) == 1
            assert view.components[0].props["label"] == "Users"

    def test_path_traversal_protection(self):
        """Should reject path traversal attempts."""
        with tempfile.TemporaryDirectory() as tmpdir:
            loader = ConfigLoader(tmpdir)

            # Try to access parent directory
            bad_path = Path(tmpdir) / ".." / "etc" / "passwd"

            with pytest.raises(ValueError, match="Path traversal"):
                loader._validate_path(bad_path)

    def test_get_config_schema(self):
        """Should return JSON schema."""
        loader = ConfigLoader()
        schema = loader.get_config_schema()

        assert schema["$schema"] == "http://json-schema.org/draft-07/schema#"
        assert "settings" in schema["properties"]
        assert "view_definition" in schema["properties"]
