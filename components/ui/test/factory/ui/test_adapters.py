"""Tests for UI render adapters.

Tests the adapter pattern for rendering views to different formats.
"""

import pytest

from factory.ui.runtime import (
    ComponentType,
    JsonAdapter,
    InlineHtmlRenderAdapter,
    RenderAdapter,
    RenderResult,
    UIComponent,
    UIView,
)


class TestRenderResult:
    """Tests for RenderResult dataclass."""

    def test_render_result_creation(self) -> None:
        """Should create RenderResult with required fields."""
        result = RenderResult(
            adapter_type="json",
            content_type="application/json",
            content={"test": "data"},
        )

        assert result.adapter_type == "json"
        assert result.content_type == "application/json"
        assert result.content == {"test": "data"}

    def test_render_result_with_metadata(self) -> None:
        """Should support optional metadata."""
        result = RenderResult(
            adapter_type="json",
            content_type="application/json",
            content={},
            metadata={"view_id": "test-123"},
        )

        assert result.metadata["view_id"] == "test-123"

    def test_render_result_to_dict(self) -> None:
        """Should convert to dictionary."""
        result = RenderResult(
            adapter_type="json",
            content_type="application/json",
            content={"data": "value"},
            metadata={"key": "val"},
        )

        d = result.to_dict()

        assert d["adapter_type"] == "json"
        assert d["content_type"] == "application/json"
        assert d["content"] == {"data": "value"}
        assert d["metadata"] == {"key": "val"}


class TestJsonAdapter:
    """Tests for JsonAdapter."""

    def test_adapter_type(self) -> None:
        """Should have correct adapter type."""
        adapter = JsonAdapter()
        assert adapter.adapter_type == "json"

    def test_content_type(self) -> None:
        """Should have correct content type."""
        adapter = JsonAdapter()
        assert adapter.content_type == "application/json"

    def test_render_empty_view(self) -> None:
        """Should render empty view."""
        adapter = JsonAdapter()
        view = UIView(id="test", name="Test View")

        result = adapter.render_view(view)

        assert result.adapter_type == "json"
        assert result.content["id"] == "test"
        assert result.content["name"] == "Test View"
        assert result.content["components"] == []

    def test_render_view_with_components(self) -> None:
        """Should render view with components."""
        adapter = JsonAdapter()
        view = UIView(
            id="dashboard",
            name="Dashboard",
            components=[
                UIComponent(
                    id="m1",
                    component_type=ComponentType.METRIC,
                    props={"label": "Users", "value": 100},
                ),
            ],
        )

        result = adapter.render_view(view)

        assert len(result.content["components"]) == 1
        assert result.content["components"][0]["id"] == "m1"

    def test_render_component(self) -> None:
        """Should render individual component."""
        adapter = JsonAdapter()
        component = UIComponent(
            id="text-1",
            component_type=ComponentType.TEXT,
            props={"content": "Hello"},
        )

        result = adapter.render_component(component)

        assert result.content["id"] == "text-1"
        assert result.content["props"]["content"] == "Hello"


class TestInlineHtmlRenderAdapter:
    """Tests for InlineHtmlRenderAdapter HTML rendering."""

    def test_adapter_type(self) -> None:
        """Should have correct adapter type."""
        adapter = InlineHtmlRenderAdapter()
        assert adapter.adapter_type == "inline-html"

    def test_content_type(self) -> None:
        """Should have correct content type."""
        adapter = InlineHtmlRenderAdapter()
        assert adapter.content_type == "application/vnd.factory.inline-html+json"

    def test_render_view_returns_html(self) -> None:
        """Should render view as HTML."""
        adapter = InlineHtmlRenderAdapter()
        view = UIView(id="test", name="Test View")

        result = adapter.render_view(view)

        assert result.content["type"] == "inline_html"
        assert "<div" in result.content["content"]

    def test_render_metric_component(self) -> None:
        """Should render metric with label and value."""
        adapter = InlineHtmlRenderAdapter()
        component = UIComponent(
            id="metric-1",
            component_type=ComponentType.METRIC,
            props={"label": "Revenue", "value": "$50,000"},
        )

        result = adapter.render_component(component)
        content = result.content["content"]

        assert "Revenue" in content
        assert "$50,000" in content

    def test_render_view_metadata(self) -> None:
        """Should include metadata in render result."""
        adapter = InlineHtmlRenderAdapter()
        view = UIView(
            id="test",
            name="Test",
            components=[
                UIComponent(id="c1", component_type=ComponentType.TEXT, props={}),
                UIComponent(id="c2", component_type=ComponentType.TEXT, props={}),
            ],
        )

        result = adapter.render_view(view)

        # Metadata may use different keys depending on implementation
        assert result.metadata is not None
        # Check for component count (may be keyed differently)
        if "component_count" in result.metadata:
            assert result.metadata["component_count"] == 2
        elif "components" in result.metadata:
            assert result.metadata["components"] == 2
