"""Tests for MCP resources."""

import json

from factory.ui import resources as res
from factory.ui.runtime import ComponentRegistry, ViewManager


class TestResources:
    """Tests for MCP resources."""

    def test_get_all_components_resource(self):
        """Should return all component schemas."""
        registry = ComponentRegistry()
        result = res.get_all_components_resource(registry)

        assert result["uri"] == "ui://components"
        content = json.loads(result["content"])
        assert "components" in content
        assert len(content["components"]) > 0

    def test_get_component_schema_resource(self):
        """Should return schema for specific component."""
        registry = ComponentRegistry()
        result = res.get_component_schema_resource("metric", registry)

        assert result["uri"] == "ui://components/metric"
        content = json.loads(result["content"])
        assert content["type"] == "metric"
        assert "schema" in content
        assert "example" in content

    def test_get_component_schema_unknown(self):
        """Should handle unknown component type."""
        registry = ComponentRegistry()
        result = res.get_component_schema_resource("unknown", registry)

        content = json.loads(result["content"])
        assert "error" in content

    def test_get_all_templates_resource(self):
        """Should return all templates."""
        result = res.get_all_templates_resource()

        assert result["uri"] == "ui://templates"
        content = json.loads(result["content"])
        assert "templates" in content
        assert "dashboard" in content["templates"]

    def test_get_template_resource(self):
        """Should return specific template."""
        result = res.get_template_resource("dashboard")

        assert result["uri"] == "ui://templates/dashboard"
        content = json.loads(result["content"])
        assert content["name"] == "Dashboard Template"
        assert "suggested_components" in content

    def test_get_view_resource(self):
        """Should return view as resource."""
        manager = ViewManager()
        manager.create_view(name="Test View", view_id="test-view")

        result = res.get_view_resource("test-view", manager)

        assert result["uri"] == "ui://views/test-view"
        content = json.loads(result["content"])
        assert content["name"] == "Test View"

    def test_get_docs_resource(self):
        """Should return documentation."""
        result = res.get_docs_resource("getting-started")

        assert result["uri"] == "ui://docs/getting-started"
        assert result["mimeType"] == "text/markdown"
        assert "# Getting Started" in result["content"]

    def test_list_all_resources(self):
        """Should list all available resources."""
        registry = ComponentRegistry()
        manager = ViewManager(registry=registry)
        manager.create_view(name="Test", view_id="test")

        resources = res.list_all_resources(registry, manager)

        # Should have components, templates, views, docs
        uris = [r["uri"] for r in resources]
        assert "ui://components" in uris
        assert "ui://templates" in uris
        assert "ui://views/test" in uris
        assert any("ui://docs/" in uri for uri in uris)
