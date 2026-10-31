"""Tests for HTMX adapter."""

import pytest

from factory.ui.runtime.adapters.htmx_adapter import HTMXAdapter
from factory.ui.runtime.models import ComponentType, UIComponent, UIView


class TestHTMXAdapter:
    """Tests for HTMXAdapter."""

    @pytest.fixture
    def adapter(self) -> HTMXAdapter:
        return HTMXAdapter()

    @pytest.fixture
    def sample_view(self) -> UIView:
        return UIView(
            id="test-view",
            name="Test Dashboard",
            components=[
                UIComponent(id="metric-1", component_type=ComponentType.METRIC, props={"label": "Users", "value": "1,234", "trend": "up"}),
                UIComponent(id="btn-1", component_type=ComponentType.BUTTON, props={"label": "Click Me", "variant": "primary"}),
            ],
            layout={"type": "grid", "columns": 2},
        )

    def test_adapter_type(self, adapter: HTMXAdapter) -> None:
        assert adapter.adapter_type == "htmx"

    def test_content_type(self, adapter: HTMXAdapter) -> None:
        assert adapter.content_type == "text/html"

    def test_supports_streaming(self, adapter: HTMXAdapter) -> None:
        assert adapter.supports_streaming() is True

    def test_render_view_returns_html(self, adapter: HTMXAdapter, sample_view: UIView) -> None:
        result = adapter.render_view(sample_view)
        assert result.adapter_type == "htmx"
        assert result.content_type == "text/html"
        assert isinstance(result.content, str)
        assert "data-view-id" in result.content
        assert "test-view" in result.content

    def test_render_view_includes_daisyui_classes(self, adapter: HTMXAdapter, sample_view: UIView) -> None:
        result = adapter.render_view(sample_view)
        # DaisyUI classes should be present
        assert "btn" in result.content
        assert "stat" in result.content

    def test_render_view_includes_htmx_boost(self, adapter: HTMXAdapter, sample_view: UIView) -> None:
        result = adapter.render_view(sample_view)
        assert 'hx-boost="true"' in result.content

    def test_render_view_without_htmx_boost(self, sample_view: UIView) -> None:
        adapter = HTMXAdapter(hx_boost=False)
        result = adapter.render_view(sample_view)
        assert 'hx-boost="true"' not in result.content

    def test_render_component_button(self, adapter: HTMXAdapter) -> None:
        btn = UIComponent(id="btn", component_type=ComponentType.BUTTON, props={"label": "Submit", "variant": "primary"})
        result = adapter.render_component(btn)
        assert "btn btn-primary" in result.content
        assert "Submit" in result.content

    def test_render_component_card(self, adapter: HTMXAdapter) -> None:
        card = UIComponent(id="card", component_type=ComponentType.CARD, props={"title": "My Card", "content": "Card content"})
        result = adapter.render_component(card)
        assert "card bg-base-100" in result.content
        assert "My Card" in result.content

    def test_render_component_table(self, adapter: HTMXAdapter) -> None:
        table = UIComponent(
            id="tbl",
            component_type=ComponentType.TABLE,
            props={"columns": [{"key": "name", "label": "Name"}], "rows": [{"name": "Alice"}]},
        )
        result = adapter.render_component(table)
        assert "table table-zebra" in result.content
        assert "Alice" in result.content  # present in Alpine JSON data

    def test_render_component_alert(self, adapter: HTMXAdapter) -> None:
        alert = UIComponent(id="alert", component_type=ComponentType.ALERT, props={"message": "Warning!", "severity": "warning"})
        result = adapter.render_component(alert)
        assert "alert alert-warning" in result.content
        assert "Warning!" in result.content

    def test_render_component_form(self, adapter: HTMXAdapter) -> None:
        form = UIComponent(
            id="form",
            component_type=ComponentType.FORM,
            props={"fields": [{"name": "email", "type": "email", "label": "Email"}], "submit_label": "Send"},
        )
        result = adapter.render_component(form)
        assert "input input-bordered" in result.content
        assert "Send" in result.content
        assert 'hx-disabled-elt="this"' in result.content

    def test_no_inline_data_theme(self, sample_view: UIView) -> None:
        """Views inherit theme from <html>, no inline data-theme."""
        adapter = HTMXAdapter()
        result = adapter.render_view(sample_view)
        assert 'data-theme=' not in result.content

    def test_grid_layout(self, adapter: HTMXAdapter, sample_view: UIView) -> None:
        result = adapter.render_view(sample_view)
        assert "grid grid-cols-2" in result.content

    def test_flex_layout(self, adapter: HTMXAdapter) -> None:
        view = UIView(id="v", name="Flex", layout={"type": "flex", "direction": "col"})
        result = adapter.render_view(view)
        assert "flex flex-col" in result.content


class TestRenderTextStyleProps:
    """GH #78 — render_text maps catalog style props color/size/align."""

    @pytest.fixture
    def adapter(self) -> HTMXAdapter:
        return HTMXAdapter()

    def _render(self, props: dict) -> str:
        c = UIComponent(id="t", component_type=ComponentType.TEXT, props=props)
        return HTMXAdapter().render_component(c).content

    def test_color_and_size_paint_inline_style(self) -> None:
        html = self._render({"content": "Daniel", "color": "#ff0099", "size": 24})
        assert "style=" in html
        assert "color: #ff0099" in html
        assert "font-size: 24px" in html

    def test_size_numeric_string_gets_px(self) -> None:
        html = self._render({"content": "x", "size": "18"})
        assert "font-size: 18px" in html

    def test_size_css_string_passes_through(self) -> None:
        html = self._render({"content": "x", "size": "1.5rem"})
        assert "font-size: 1.5rem" in html

    def test_align_maps_to_text_align(self) -> None:
        html = self._render({"content": "x", "align": "center"})
        assert "text-align: center" in html

    def test_no_style_props_no_style_attr(self) -> None:
        html = self._render({"content": "plain"})
        assert "style=" not in html

    def test_canonical_text_prop_renders_content(self) -> None:
        """GH #78 — canonical 'text' prop must render (matches React renderer)."""
        html = self._render({"text": "Hello", "color": "#00ff00"})
        assert ">Hello</p>" in html
        assert "color: #00ff00" in html

    def test_value_alias_renders_content(self) -> None:
        html = self._render({"value": "Via value"})
        assert ">Via value</p>" in html
