"""Tests for InlineHtmlRenderAdapter (renamed from McpUiAdapter under
bd:python-factory-kxpnf, re-run under bd:python-factory-lo1g9.0)."""

from factory.ui.runtime import (
    ComponentType,
    InlineHtmlRenderAdapter,
    UIComponent,
    UIView,
)
from factory.ui.runtime.adapters.inline_html_adapter import UIResourceType


class TestInlineHtmlRenderAdapter:
    """Tests for InlineHtmlRenderAdapter."""

    def test_adapter_type(self):
        """Should have correct adapter type."""
        adapter = InlineHtmlRenderAdapter()
        assert adapter.adapter_type == "inline-html"

    def test_content_type(self):
        """Should have correct content type."""
        adapter = InlineHtmlRenderAdapter()
        assert adapter.content_type == "application/vnd.factory.inline-html+json"

    def test_render_view(self):
        """Should render view as UIResource."""
        adapter = InlineHtmlRenderAdapter()
        view = UIView(id="test", name="Test View")

        result = adapter.render_view(view)

        assert result.adapter_type == "inline-html"
        assert result.content["type"] == "inline_html"
        assert '<div class="mcp-ui-view"' in result.content["content"]

    def test_render_text_component(self):
        """Should render text component."""
        adapter = InlineHtmlRenderAdapter()
        component = UIComponent(
            id="text-1",
            component_type=ComponentType.TEXT,
            props={"content": "Hello World", "variant": "h1"},
        )

        result = adapter.render_component(component)

        assert "<h1" in result.content["content"]
        assert "Hello World" in result.content["content"]

    def test_render_metric_component(self):
        """Should render metric component."""
        adapter = InlineHtmlRenderAdapter()
        component = UIComponent(
            id="metric-1",
            component_type=ComponentType.METRIC,
            props={"label": "Revenue", "value": "$50,000", "trend": "up"},
        )

        result = adapter.render_component(component)
        content = result.content["content"]

        assert "mcp-ui-metric" in content
        assert "Revenue" in content
        assert "$50,000" in content
        assert "trend--up" in content

    def test_render_table_component(self):
        """Should render table component."""
        adapter = InlineHtmlRenderAdapter()
        component = UIComponent(
            id="table-1",
            component_type=ComponentType.TABLE,
            props={
                "columns": [{"key": "name", "label": "Name"}, {"key": "value", "label": "Value"}],
                "rows": [{"name": "Item 1", "value": 100}],
            },
        )

        result = adapter.render_component(component)
        content = result.content["content"]

        assert "<table" in content
        assert "<th>Name" in content
        assert "Item 1" in content

    def test_render_alert_component(self):
        """Should render alert with severity."""
        adapter = InlineHtmlRenderAdapter()
        component = UIComponent(
            id="alert-1",
            component_type=ComponentType.ALERT,
            props={"message": "Warning!", "severity": "warning"},
        )

        result = adapter.render_component(component)
        content = result.content["content"]

        assert "mcp-ui-alert--warning" in content
        assert "Warning!" in content

    def test_render_view_with_components(self):
        """Should render view with multiple components."""
        adapter = InlineHtmlRenderAdapter()
        view = UIView(
            id="dashboard",
            name="Dashboard",
            components=[
                UIComponent(
                    id="m1",
                    component_type=ComponentType.METRIC,
                    props={"label": "Users", "value": 100},
                ),
                UIComponent(
                    id="m2",
                    component_type=ComponentType.METRIC,
                    props={"label": "Sales", "value": 500},
                ),
            ],
        )

        result = adapter.render_view(view)
        content = result.content["content"]

        assert "Users" in content
        assert "Sales" in content
        assert result.metadata["component_count"] == 2

    def test_resource_type_configuration(self):
        """Should respect resource type configuration."""
        adapter = InlineHtmlRenderAdapter(resource_type=UIResourceType.INLINE_HTML)
        view = UIView(id="test", name="Test")

        result = adapter.render_view(view)

        assert result.content["type"] == "inline_html"
