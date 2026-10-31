"""Unit tests for AGUIAdapter.

Tests adapter properties, render delegation, state methods,
render_view (MESSAGES_SNAPSHOT), and render_component (CUSTOM).
"""

import pytest

from factory.ui.runtime.adapters.ag_ui_adapter import AGUIAdapter
from factory.ui.runtime.adapters.base import RenderAdapter, RenderResult
from factory.ui.runtime.ag_ui_mapper import AGUIEventType
from factory.ui.runtime.models import ComponentType, UIComponent, UIView


class TestAdapterProperties:
    @pytest.fixture
    def adapter(self) -> AGUIAdapter:
        return AGUIAdapter()

    def test_adapter_type(self, adapter: AGUIAdapter) -> None:
        assert adapter.adapter_type == "ag-ui"

    def test_content_type(self, adapter: AGUIAdapter) -> None:
        assert adapter.content_type == "text/event-stream"

    def test_supports_streaming(self, adapter: AGUIAdapter) -> None:
        assert adapter.supports_streaming() is True

    def test_is_render_adapter(self, adapter: AGUIAdapter) -> None:
        assert isinstance(adapter, RenderAdapter)


class TestRenderEvent:
    @pytest.fixture
    def adapter(self) -> AGUIAdapter:
        return AGUIAdapter()

    def test_delegates_to_mapper(self, adapter: AGUIAdapter) -> None:
        event = {"type": "agent.session.start", "payload": {}, "session_id": "s1"}
        result = adapter.render_event(event)
        assert isinstance(result, list)
        assert len(result) == 1
        assert result[0]["type"] == AGUIEventType.RUN_STARTED

    def test_text_event_returns_three_events(self, adapter: AGUIAdapter) -> None:
        event = {"type": "agent.output.text", "payload": {"text": "hi"}}
        result = adapter.render_event(event)
        assert len(result) == 3
        types = [e["type"] for e in result]
        assert types == [
            AGUIEventType.TEXT_MESSAGE_START,
            AGUIEventType.TEXT_MESSAGE_CONTENT,
            AGUIEventType.TEXT_MESSAGE_END,
        ]

    def test_tool_call_returns_three_events(self, adapter: AGUIAdapter) -> None:
        event = {"type": "agent.tool.call", "payload": {"tool_name": "x"}}
        result = adapter.render_event(event)
        assert len(result) == 3
        types = [e["type"] for e in result]
        assert types == [
            AGUIEventType.TOOL_CALL_START,
            AGUIEventType.TOOL_CALL_ARGS,
            AGUIEventType.TOOL_CALL_END,
        ]

    def test_unknown_event_returns_custom(self, adapter: AGUIAdapter) -> None:
        event = {"type": "unknown.thing", "payload": {"x": 1}}
        result = adapter.render_event(event)
        assert len(result) == 1
        assert result[0]["type"] == AGUIEventType.CUSTOM


class TestRenderStateSnapshot:
    @pytest.fixture
    def adapter(self) -> AGUIAdapter:
        return AGUIAdapter()

    def test_produces_state_snapshot(self, adapter: AGUIAdapter) -> None:
        result = adapter.render_state_snapshot({"key": "val"})
        assert result["type"] == AGUIEventType.STATE_SNAPSHOT
        assert result["snapshot"] == {"key": "val"}
        assert "timestamp" in result

    def test_empty_state(self, adapter: AGUIAdapter) -> None:
        result = adapter.render_state_snapshot({})
        assert result["snapshot"] == {}


class TestRenderStateDelta:
    @pytest.fixture
    def adapter(self) -> AGUIAdapter:
        return AGUIAdapter()

    def test_produces_state_delta(self, adapter: AGUIAdapter) -> None:
        patch = [{"op": "add", "path": "/x", "value": 1}]
        result = adapter.render_state_delta(patch)
        assert result["type"] == AGUIEventType.STATE_DELTA
        assert result["delta"] == patch
        assert "timestamp" in result

    def test_empty_patch(self, adapter: AGUIAdapter) -> None:
        result = adapter.render_state_delta([])
        assert result["delta"] == []


class TestRenderView:
    @pytest.fixture
    def adapter(self) -> AGUIAdapter:
        return AGUIAdapter()

    @pytest.fixture
    def sample_view(self) -> UIView:
        return UIView(id="v1", name="Dashboard")

    def test_produces_messages_snapshot(self, adapter: AGUIAdapter, sample_view: UIView) -> None:
        result = adapter.render_view(sample_view)
        assert isinstance(result, RenderResult)
        assert result.content["type"] == AGUIEventType.MESSAGES_SNAPSHOT
        assert result.content_type == "text/event-stream"
        assert result.adapter_type == "ag-ui"

    def test_messages_contain_view_info(self, adapter: AGUIAdapter, sample_view: UIView) -> None:
        result = adapter.render_view(sample_view)
        msgs = result.content["messages"]
        assert len(msgs) == 1
        assert msgs[0]["id"] == "v1"
        assert msgs[0]["role"] == "assistant"
        assert msgs[0]["content"] == "Dashboard"

    def test_metadata_includes_ag_ui_flag(self, adapter: AGUIAdapter, sample_view: UIView) -> None:
        result = adapter.render_view(sample_view)
        assert result.metadata["ag_ui"] is True
        assert result.metadata["view_id"] == "v1"


class TestRenderComponent:
    @pytest.fixture
    def adapter(self) -> AGUIAdapter:
        return AGUIAdapter()

    def test_produces_custom_event(self, adapter: AGUIAdapter) -> None:
        comp = UIComponent(id="c1", component_type=ComponentType.BUTTON,
                           props={"label": "Go"})
        result = adapter.render_component(comp)
        assert isinstance(result, RenderResult)
        assert result.content["type"] == AGUIEventType.CUSTOM
        assert result.content["name"] == "component"

    def test_component_dict_in_value(self, adapter: AGUIAdapter) -> None:
        comp = UIComponent(id="c2", component_type=ComponentType.TEXT,
                           props={"content": "hi"})
        result = adapter.render_component(comp)
        val = result.content["value"]
        assert val["id"] == "c2"
        assert val["type"] == "text"

    def test_metadata_has_ag_ui_flag(self, adapter: AGUIAdapter) -> None:
        comp = UIComponent(id="c3", component_type=ComponentType.CARD)
        result = adapter.render_component(comp)
        assert result.metadata["ag_ui"] is True
