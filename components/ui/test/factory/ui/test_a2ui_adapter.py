"""Tests for A2UI adapter and renderer."""

import pytest
from factory.ui.runtime.a2ui import (
    a2ui_to_ui_view,
    ui_view_to_a2ui,
)
from factory.ui.runtime.adapters import A2UIAdapter, A2UIConfig, create_a2ui_adapter


class TestA2UIRenderer:
    """Tests for A2UI to native UI conversion."""

    def test_a2ui_to_ui_view(self):
        """Convert A2UI payload to UIView."""
        payload = {
            "components": [
                {"id": "1", "type": "Card", "props": {"title": "Dashboard"}},
                {"id": "2", "type": "Text", "parent": "1", "props": {"content": "Welcome"}},
            ]
        }
        view = a2ui_to_ui_view(payload, view_name="Test View")
        
        assert view.name == "Test View"
        assert len(view.components) == 1  # Only root
        assert view.components[0].id == "1"
        assert len(view.components[0].children) == 1
        assert view.components[0].children[0].id == "2"
        assert view.metadata.get("source") == "a2ui"

    def test_ui_view_to_a2ui(self):
        """Convert UIView back to A2UI format."""
        payload = {
            "components": [
                {"id": "1", "type": "Card", "props": {"title": "Test"}},
            ]
        }
        view = a2ui_to_ui_view(payload)
        result = ui_view_to_a2ui(view)
        
        assert "components" in result
        assert len(result["components"]) == 1
        assert result["components"][0]["type"] == "Card"


class TestA2UIAdapter:
    """Tests for A2UI adapter."""

    def test_create_adapter_htmx(self):
        """Create adapter with HTMX backend."""
        adapter = create_a2ui_adapter(backend="htmx")
        assert "htmx" in adapter.adapter_type
        assert adapter.content_type == "text/html"

    def test_create_adapter_react(self):
        """Create adapter with React backend."""
        adapter = create_a2ui_adapter(backend="react")
        assert "react" in adapter.adapter_type

    def test_create_adapter_json(self):
        """Create adapter with JSON backend."""
        adapter = create_a2ui_adapter(backend="json")
        assert "json" in adapter.adapter_type

    def test_render_a2ui(self):
        """Render A2UI payload."""
        adapter = create_a2ui_adapter(backend="json")
        payload = {
            "components": [
                {"id": "1", "type": "Card", "props": {"title": "Test"}},
            ]
        }
        result = adapter.render_a2ui(payload)
        
        assert result.metadata.get("a2ui") is True
        assert result.content is not None

    def test_render_invalid_payload_strict(self):
        """Invalid payload raises with strict validation."""
        adapter = create_a2ui_adapter(backend="json")
        adapter._config.strict_validation = True
        
        with pytest.raises(ValueError):
            adapter.render_a2ui({"components": [{"type": "Card"}]})  # Missing id

    def test_supports_streaming(self):
        """A2UI adapter supports streaming."""
        adapter = create_a2ui_adapter()
        assert adapter.supports_streaming() is True

    def test_get_component_catalog(self):
        """Get component catalog from adapter."""
        adapter = create_a2ui_adapter()
        catalog = adapter.get_component_catalog()
        assert len(catalog) > 0
