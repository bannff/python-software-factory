"""Tests for Hybrid adapter."""

import pytest

from factory.ui.runtime.adapters.hybrid_adapter import HybridAdapter
from factory.ui.runtime.models import ComponentType, UIComponent, UIView


class TestHybridAdapter:
    """Tests for HybridAdapter."""

    @pytest.fixture
    def adapter(self) -> HybridAdapter:
        return HybridAdapter()

    @pytest.fixture
    def sample_view(self) -> UIView:
        return UIView(
            id="test-view",
            name="Test View",
            components=[UIComponent(id="txt", component_type=ComponentType.TEXT, props={"content": "Hello"})],
        )

    def test_adapter_type(self, adapter: HybridAdapter) -> None:
        assert adapter.adapter_type == "hybrid"

    def test_default_route_map(self, adapter: HybridAdapter) -> None:
        route_map = adapter.get_route_map()
        assert "/admin/*" in route_map
        assert "/app/*" in route_map
        assert route_map["/admin/*"] == "htmx"
        assert route_map["/app/*"] == "react"

    def test_admin_route_uses_htmx(self, adapter: HybridAdapter, sample_view: UIView) -> None:
        result = adapter.render_view(sample_view, route="/admin/dashboard")
        assert result.metadata["selected_adapter"] == "htmx"
        assert result.content_type == "text/html"

    def test_app_route_uses_react(self, adapter: HybridAdapter, sample_view: UIView) -> None:
        result = adapter.render_view(sample_view, route="/app/home")
        assert result.metadata["selected_adapter"] == "react"
        assert result.content_type == "application/json"

    def test_api_route_uses_json(self, adapter: HybridAdapter, sample_view: UIView) -> None:
        result = adapter.render_view(sample_view, route="/api/ui/views")
        assert result.metadata["selected_adapter"] == "json"
        assert result.content_type == "application/json"

    def test_unknown_route_uses_default(self, adapter: HybridAdapter, sample_view: UIView) -> None:
        result = adapter.render_view(sample_view, route="/unknown/path")
        assert result.metadata["selected_adapter"] == "json"  # default

    def test_no_route_uses_default(self, adapter: HybridAdapter, sample_view: UIView) -> None:
        result = adapter.render_view(sample_view)
        assert result.metadata["selected_adapter"] == "json"

    def test_custom_route_map(self, sample_view: UIView) -> None:
        adapter = HybridAdapter(route_map={"/custom/*": "htmx"}, default_adapter="react")
        result = adapter.render_view(sample_view, route="/custom/page")
        assert result.metadata["selected_adapter"] == "htmx"

    def test_custom_default_adapter(self, sample_view: UIView) -> None:
        adapter = HybridAdapter(default_adapter="htmx")
        result = adapter.render_view(sample_view, route="/unknown")
        assert result.metadata["selected_adapter"] == "htmx"

    def test_set_route_map(self, adapter: HybridAdapter, sample_view: UIView) -> None:
        adapter.set_route_map({"/new/*": "react"})
        result = adapter.render_view(sample_view, route="/new/page")
        assert result.metadata["selected_adapter"] == "react"

    def test_set_route_persists(self, adapter: HybridAdapter, sample_view: UIView) -> None:
        adapter.set_route("/admin/users")
        result = adapter.render_view(sample_view)
        assert result.metadata["selected_adapter"] == "htmx"

    def test_get_adapter(self, adapter: HybridAdapter) -> None:
        htmx = adapter.get_adapter("htmx")
        assert htmx is not None
        assert htmx.adapter_type == "htmx"

    def test_register_custom_adapter(self, adapter: HybridAdapter) -> None:
        from factory.ui.runtime.adapters.inline_html_adapter import InlineHtmlRenderAdapter
        adapter.register_adapter("custom", InlineHtmlRenderAdapter())
        assert adapter.get_adapter("custom") is not None

    def test_to_dict(self, adapter: HybridAdapter) -> None:
        data = adapter.to_dict()
        assert data["adapter_type"] == "hybrid"
        assert "route_map" in data
        assert "available_adapters" in data
        assert "htmx" in data["available_adapters"]
        assert "react" in data["available_adapters"]

    def test_supports_streaming(self, adapter: HybridAdapter) -> None:
        assert adapter.supports_streaming() is True

    def test_wildcard_matching(self, adapter: HybridAdapter, sample_view: UIView) -> None:
        # Test nested paths match wildcard
        result = adapter.render_view(sample_view, route="/admin/users/123/edit")
        assert result.metadata["selected_adapter"] == "htmx"

    def test_exact_match(self, sample_view: UIView) -> None:
        adapter = HybridAdapter(route_map={"/exact": "htmx"})
        result = adapter.render_view(sample_view, route="/exact")
        assert result.metadata["selected_adapter"] == "htmx"
        # But not for subpaths
        result2 = adapter.render_view(sample_view, route="/exact/sub")
        assert result2.metadata["selected_adapter"] == "json"  # default
