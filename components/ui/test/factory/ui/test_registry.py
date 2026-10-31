"""Tests for component registry."""

from factory.ui.runtime import (
    ComponentDefinition,
    ComponentRegistry,
    ComponentType,
)


class TestComponentRegistry:
    """Tests for ComponentRegistry."""

    def test_builtins_registered(self):
        """Built-in components should be registered on init."""
        registry = ComponentRegistry()
        components = registry.list_components()

        assert len(components) > 0
        types = [c.component_type for c in components]
        assert ComponentType.TEXT in types
        assert ComponentType.CHART in types
        assert ComponentType.TABLE in types
        assert ComponentType.METRIC in types

    def test_get_component(self):
        """Should retrieve component definition by type."""
        registry = ComponentRegistry()
        text_def = registry.get(ComponentType.TEXT)

        assert text_def is not None
        assert text_def.name == "Text"
        assert "content" in text_def.schema["properties"]

    def test_register_custom(self):
        """Should register custom component types."""
        registry = ComponentRegistry()

        custom = ComponentDefinition(
            component_type=ComponentType.CUSTOM,
            name="MyWidget",
            description="A custom widget",
            schema={"type": "object", "properties": {"data": {"type": "string"}}},
        )
        registry.register(custom)

        retrieved = registry.get(ComponentType.CUSTOM)
        assert retrieved is not None
        assert retrieved.name == "MyWidget"

    def test_create_component_with_defaults(self):
        """Should apply default props when creating components."""
        registry = ComponentRegistry()

        component = registry.create_component(
            component_id="test-1",
            component_type=ComponentType.TEXT,
            props={"content": "Hello"},
        )

        assert component.id == "test-1"
        assert component.props["content"] == "Hello"
        assert component.props["variant"] == "body"  # default

    def test_create_component_override_defaults(self):
        """Should allow overriding default props."""
        registry = ComponentRegistry()

        component = registry.create_component(
            component_id="test-2",
            component_type=ComponentType.TEXT,
            props={"content": "Title", "variant": "h1"},
        )

        assert component.props["variant"] == "h1"

    def test_to_dict(self):
        """Should export registry as dictionary."""
        registry = ComponentRegistry()
        data = registry.to_dict()

        assert "components" in data
        assert len(data["components"]) > 0
        assert all("type" in c for c in data["components"])
