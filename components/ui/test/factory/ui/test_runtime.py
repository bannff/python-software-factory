"""Tests for UIRuntime."""

from factory.ui.runtime import UIRuntime, reset_runtime


class TestUIRuntime:
    """Tests for UIRuntime."""

    def setup_method(self):
        """Reset runtime before each test."""
        reset_runtime()

    def test_initialize(self):
        """Should initialize runtime."""
        runtime = UIRuntime()
        runtime.initialize()

        assert runtime._initialized is True
        assert runtime.settings is not None
        assert runtime.view_manager is not None

    def test_get_capabilities(self):
        """Should return capabilities."""
        runtime = UIRuntime()
        runtime.initialize()

        caps = runtime.get_capabilities()

        assert caps["module"] == "ui-module"
        assert "version" in caps
        assert "schema_version" in caps
        assert "adapters" in caps
        assert "component_types" in caps

    def test_health_check_healthy(self):
        """Should return healthy status."""
        runtime = UIRuntime()
        runtime.initialize()

        health = runtime.health_check()

        assert health["status"] == "healthy"
        assert health["checks"]["initialized"]["status"] == "ok"
        assert health["checks"]["store"]["status"] == "ok"

    def test_health_check_not_initialized(self):
        """Should return unhealthy when not initialized."""
        runtime = UIRuntime()
        # Don't initialize

        health = runtime.health_check()

        # Runtime returns simple status when not initialized
        assert health.get("status") in ("unhealthy", "not_initialized")

    def test_describe_config_schema(self):
        """Should return config schema."""
        runtime = UIRuntime()

        schema = runtime.describe_config_schema()

        assert "$schema" in schema
        assert "properties" in schema
        assert "settings" in schema["properties"]
        assert "view_definition" in schema["properties"]

    def test_get_view_registry(self):
        """Should return view registry."""
        runtime = UIRuntime()
        runtime.initialize()

        # Create a view
        runtime.view_manager.create_view(name="Test View")

        registry = runtime.get_view_registry()

        assert registry["total"] == 1
        assert len(registry["views"]) == 1
        assert registry["views"][0]["name"] == "Test View"

    def test_get_authoring_status(self):
        """Should return authoring status."""
        runtime = UIRuntime()
        runtime.initialize()

        status = runtime.get_authoring_status()

        assert "enabled" in status
        assert "config_dir" in status
        assert "views_dir" in status
