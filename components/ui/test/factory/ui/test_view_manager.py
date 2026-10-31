"""Tests for ViewManager."""

import pytest

from factory.ui.runtime import (
    ComponentType,
    ViewManager,
)


class TestViewManager:
    """Tests for ViewManager."""

    def test_create_view(self):
        """Should create a new view."""
        manager = ViewManager()
        view = manager.create_view(name="Test Dashboard")

        assert view.name == "Test Dashboard"
        assert view.id is not None
        assert view.version == 1

    def test_create_view_with_custom_id(self):
        """Should create view with custom ID."""
        manager = ViewManager()
        view = manager.create_view(name="Test", view_id="my-view")

        assert view.id == "my-view"

    def test_get_view(self):
        """Should retrieve view by ID."""
        manager = ViewManager()
        created = manager.create_view(name="Test")

        retrieved = manager.get_view(created.id)
        assert retrieved is not None
        assert retrieved.name == "Test"

    def test_get_view_not_found(self):
        """Should return None for non-existent view."""
        manager = ViewManager()
        assert manager.get_view("nonexistent") is None

    def test_delete_view(self):
        """Should delete a view."""
        manager = ViewManager()
        view = manager.create_view(name="Test")

        assert manager.delete_view(view.id) is True
        assert manager.get_view(view.id) is None

    def test_list_views(self):
        """Should list all views."""
        manager = ViewManager()
        manager.create_view(name="View 1")
        manager.create_view(name="View 2")

        views = manager.list_views()
        assert len(views) == 2

    def test_create_component(self):
        """Should create component via registry."""
        manager = ViewManager()
        component = manager.create_component(
            component_type="text",
            props={"content": "Hello"},
        )

        assert component.component_type == ComponentType.TEXT
        assert component.props["content"] == "Hello"

    @pytest.mark.asyncio
    async def test_add_component(self):
        """Should add component to view."""
        manager = ViewManager()
        view = manager.create_view(name="Test")
        component = manager.create_component(
            component_type="metric",
            props={"label": "Users", "value": 100},
        )

        updated = await manager.add_component(view.id, component)

        assert updated is not None
        assert len(updated.components) == 1
        assert updated.components[0].props["label"] == "Users"

    @pytest.mark.asyncio
    async def test_update_component(self):
        """Should update component props."""
        manager = ViewManager()
        view = manager.create_view(name="Test")
        component = manager.create_component(
            component_type="metric",
            props={"label": "Users", "value": 100},
        )
        await manager.add_component(view.id, component)

        updated = await manager.update_component(
            view.id,
            component.id,
            props={"value": 200},
        )

        assert updated is not None
        assert updated.props["value"] == 200
        assert updated.props["label"] == "Users"  # unchanged

    @pytest.mark.asyncio
    async def test_remove_component(self):
        """Should remove component from view."""
        manager = ViewManager()
        view = manager.create_view(name="Test")
        component = manager.create_component(component_type="text", props={"content": "Hi"})
        await manager.add_component(view.id, component)

        removed = await manager.remove_component(view.id, component.id)

        assert removed is True
        updated_view = manager.get_view(view.id)
        assert len(updated_view.components) == 0

    def test_render_json(self):
        """Should render view as JSON."""
        manager = ViewManager()
        view = manager.create_view(name="Test")

        result = manager.render(view.id, adapter_type="json")

        assert result is not None
        assert result.adapter_type == "json"
        assert result.content["name"] == "Test"

    def test_render_mcpui(self):
        """Should render view as MCP-UI."""
        manager = ViewManager()
        view = manager.create_view(name="Test")

        result = manager.render(view.id, adapter_type="inline-html")

        assert result is not None
        assert result.adapter_type == "inline-html"
        assert "inline_html" in result.content["type"]

    def test_list_adapters(self):
        """Should list available adapters with metadata."""
        manager = ViewManager()
        adapters = manager.list_adapters()

        # Now returns list of dicts with metadata
        adapter_types = [a["type"] for a in adapters]
        assert "json" in adapter_types
        assert "inline-html" in adapter_types
        assert "a2ui-htmx" in adapter_types
        assert "a2ui-react" in adapter_types
        assert "hybrid" in adapter_types
        # Each adapter has metadata
        assert all("content_type" in a for a in adapters)
        assert all("streaming" in a for a in adapters)
