"""Tests for Flet adapter — verifies ft.Control output."""

import pytest
ft = pytest.importorskip("flet", reason="Flet renderer tests require the optional UI backend")

from factory.ui.runtime.adapters.flet_adapter import FletAdapter
from factory.ui.runtime.models import UIComponent, UIView, ComponentType


@pytest.fixture
def adapter():
    return FletAdapter(theme="light")


@pytest.fixture
def sample_view():
    return UIView(
        id="test-view",
        name="Test View",
        components=[
            UIComponent(id="t1", component_type=ComponentType.TEXT,
                        props={"content": "Hello World", "size": "lg"}),
            UIComponent(id="b1", component_type=ComponentType.BUTTON,
                        props={"label": "Click Me", "variant": "filled"}),
        ],
        layout={"type": "column", "spacing": 16},
    )


class TestFletAdapter:
    def test_adapter_type(self, adapter):
        assert adapter.adapter_type == "flet"

    def test_content_type(self, adapter):
        assert adapter.content_type == "application/x-flet-control"

    def test_supports_streaming(self, adapter):
        assert adapter.supports_streaming() is True

    def test_render_view_returns_control(self, adapter, sample_view):
        result = adapter.render_view(sample_view)
        assert result.adapter_type == "flet"
        assert isinstance(result.content, ft.Control)
        assert result.metadata["component_count"] == 2

    def test_render_text(self, adapter):
        c = UIComponent(id="t", component_type=ComponentType.TEXT,
                        props={"content": "Hello", "size": "lg", "bold": True})
        result = adapter.render_component(c)
        assert isinstance(result.content, ft.Text)
        assert result.content.value == "Hello"
        assert result.content.size == 18

    def test_render_button(self, adapter):
        c = UIComponent(id="b", component_type=ComponentType.BUTTON,
                        props={"label": "Submit", "variant": "outlined"})
        result = adapter.render_component(c)
        assert isinstance(result.content, ft.OutlinedButton)

    def test_render_metric(self, adapter):
        c = UIComponent(id="m", component_type=ComponentType.METRIC,
                        props={"label": "Users", "value": 1234, "change": "+5%"})
        result = adapter.render_component(c)
        assert isinstance(result.content, ft.Container)

    def test_render_alert(self, adapter):
        c = UIComponent(id="a", component_type=ComponentType.ALERT,
                        props={"message": "OK", "severity": "success"})
        result = adapter.render_component(c)
        assert isinstance(result.content, ft.Container)

    def test_render_progress_bar(self, adapter):
        c = UIComponent(id="p", component_type=ComponentType.PROGRESS,
                        props={"value": 75, "max": 100})
        result = adapter.render_component(c)
        assert isinstance(result.content, ft.ProgressBar)

    def test_render_progress_ring(self, adapter):
        c = UIComponent(id="p", component_type=ComponentType.PROGRESS,
                        props={"value": 50, "max": 100, "circular": True})
        result = adapter.render_component(c)
        assert isinstance(result.content, ft.ProgressRing)

    def test_render_table(self, adapter):
        c = UIComponent(id="t", component_type=ComponentType.TABLE,
                        props={"columns": ["Name", "Age"],
                               "rows": [["Alice", 30], ["Bob", 25]]})
        result = adapter.render_component(c)
        assert isinstance(result.content, ft.Container)

    def test_render_list(self, adapter):
        c = UIComponent(id="l", component_type=ComponentType.LIST,
                        props={"items": [{"title": "A"}, {"title": "B"}]})
        result = adapter.render_component(c)
        assert isinstance(result.content, ft.ListView)

    def test_render_image(self, adapter):
        c = UIComponent(id="i", component_type=ComponentType.IMAGE,
                        props={"src": "https://example.com/img.png"})
        result = adapter.render_component(c)
        assert isinstance(result.content, ft.Image)

    def test_render_card_with_children(self, adapter):
        c = UIComponent(
            id="c", component_type=ComponentType.CARD,
            props={"title": "My Card"},
            children=[UIComponent(id="ct", component_type=ComponentType.TEXT,
                                  props={"content": "Card content"})],
        )
        result = adapter.render_component(c)
        assert isinstance(result.content, ft.Container)

    def test_render_form(self, adapter):
        c = UIComponent(
            id="f", component_type=ComponentType.FORM,
            props={"fields": [{"label": "Name", "type": "text"},
                              {"label": "Pw", "type": "password"}],
                   "submit_label": "Login"},
        )
        result = adapter.render_component(c)
        assert isinstance(result.content, ft.Container)

    def test_render_graph_viewer_empty(self, adapter):
        c = UIComponent(id="g", component_type=ComponentType.GRAPH_VIEWER,
                        props={"entities": [], "relationships": []})
        result = adapter.render_component(c)
        assert isinstance(result.content, ft.Control)

    def test_all_component_types_have_renderers(self, adapter):
        """Every ComponentType should produce a ft.Control, not crash."""
        for ctype in ComponentType:
            c = UIComponent(id=f"test-{ctype.value}",
                            component_type=ctype, props={})
            result = adapter.render_component(c)
            assert isinstance(result.content, ft.Control), (
                f"{ctype} did not produce ft.Control")
