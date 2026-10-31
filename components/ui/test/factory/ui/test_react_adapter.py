"""Tests for React/shadcn adapter."""

import pytest

from factory.ui.runtime.adapters.react_adapter import ReactAdapter
from factory.ui.runtime.adapters.react_transforms import SHADCN_COMPONENT_MAP
from factory.ui.runtime.models import ComponentType, UIComponent, UIView


class TestReactAdapter:
    """Tests for ReactAdapter."""

    @pytest.fixture
    def adapter(self) -> ReactAdapter:
        return ReactAdapter(theme="default")

    @pytest.fixture
    def sample_view(self) -> UIView:
        return UIView(
            id="test-view",
            name="Test Dashboard",
            components=[
                UIComponent(id="card-1", component_type=ComponentType.CARD, props={"title": "Stats"}),
                UIComponent(id="btn-1", component_type=ComponentType.BUTTON, props={"label": "Action", "variant": "primary"}),
            ],
            layout={"type": "grid", "columns": 3},
        )

    def test_adapter_type(self, adapter: ReactAdapter) -> None:
        assert adapter.adapter_type == "react"

    def test_content_type(self, adapter: ReactAdapter) -> None:
        assert adapter.content_type == "application/json"

    def test_supports_streaming(self, adapter: ReactAdapter) -> None:
        assert adapter.supports_streaming() is True

    def test_render_view_returns_json(self, adapter: ReactAdapter, sample_view: UIView) -> None:
        result = adapter.render_view(sample_view)
        assert result.adapter_type == "react"
        assert result.content_type == "application/json"
        assert isinstance(result.content, dict)

    def test_render_view_structure(self, adapter: ReactAdapter, sample_view: UIView) -> None:
        result = adapter.render_view(sample_view)
        content = result.content
        assert content["type"] == "view"
        assert content["id"] == "test-view"
        assert content["name"] == "Test Dashboard"
        assert "components" in content
        assert "layout" in content
        assert "theme" in content

    def test_component_mapping(self, adapter: ReactAdapter, sample_view: UIView) -> None:
        result = adapter.render_view(sample_view)
        components = result.content["components"]
        # Card should map to shadcn Card
        assert components[0]["component"] == "Card"
        assert components[0]["originalType"] == "card"
        # Button should map to shadcn Button
        assert components[1]["component"] == "Button"

    def test_variant_mapping(self, adapter: ReactAdapter) -> None:
        btn = UIComponent(id="btn", component_type=ComponentType.BUTTON, props={"variant": "danger"})
        result = adapter.render_component(btn)
        # "danger" should map to "destructive" in shadcn
        assert result.content["props"]["variant"] == "destructive"

    def test_alert_severity_mapping(self, adapter: ReactAdapter) -> None:
        alert = UIComponent(id="alert", component_type=ComponentType.ALERT, props={"severity": "error"})
        result = adapter.render_component(alert)
        assert result.content["props"]["variant"] == "destructive"

    def test_layout_transformation(self, adapter: ReactAdapter, sample_view: UIView) -> None:
        result = adapter.render_view(sample_view)
        layout = result.content["layout"]
        assert layout["type"] == "grid"
        assert layout["columns"] == 3
        assert "className" in layout

    def test_theme_tokens_included(self, adapter: ReactAdapter, sample_view: UIView) -> None:
        result = adapter.render_view(sample_view)
        theme = result.content["theme"]
        assert "background" in theme
        assert "primary" in theme
        assert "destructive" in theme

    def test_dark_theme(self, sample_view: UIView) -> None:
        adapter = ReactAdapter(theme="dark")
        result = adapter.render_view(sample_view)
        theme = result.content["theme"]
        # Dark theme has different background
        assert "222.2 84% 4.9%" in theme["background"]

    def test_animation_hints_included(self, adapter: ReactAdapter) -> None:
        card = UIComponent(id="card", component_type=ComponentType.CARD, props={})
        result = adapter.render_component(card)
        assert "animation" in result.content
        assert result.content["animation"]["library"] == "magic-ui"

    def test_animation_hints_disabled(self) -> None:
        adapter = ReactAdapter(include_animations=False)
        card = UIComponent(id="card", component_type=ComponentType.CARD, props={})
        result = adapter.render_component(card)
        assert result.content.get("animation") is None

    def test_children_transformed(self, adapter: ReactAdapter) -> None:
        parent = UIComponent(
            id="parent",
            component_type=ComponentType.CARD,
            props={"title": "Parent"},
            children=[UIComponent(id="child", component_type=ComponentType.TEXT, props={"content": "Hello"})],
        )
        result = adapter.render_component(parent)
        assert "children" in result.content
        assert len(result.content["children"]) == 1
        assert result.content["children"][0]["component"] == "Typography"

    def test_component_map_coverage(self) -> None:
        """Ensure all component types have mappings."""
        for ctype in ComponentType:
            assert ctype in SHADCN_COMPONENT_MAP, f"Missing mapping for {ctype}"
