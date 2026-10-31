"""Pin ``workflow_report_target.build_target_profile`` to typed tool.

Tracked under bd python-factory-ky0i / epic python-factory-kzd8. The
old f-string Cypher returned ``cypher_not_supported`` on networkx, so
the target profile silently came back as ``unknown`` for every local
experiment report. After migration the writer goes through
``graph_graph_get_target_app`` which is parameterized inside the typed
graph tool layer.
"""
from __future__ import annotations

import pathlib
from typing import Any

from hypothesis import given, settings, strategies as st

from factory.games.runtime.workflow_report_target import build_target_profile
from factory.graph.mcp.core_models import EntityData, EntityLookupData
from factory.mcp_utils.runtime.tool_result import ToolResult


class _Invoker:
    """Recording invoker with a configurable target-app envelope."""

    def __init__(self, envelope: dict[str, Any] | None = None) -> None:
        self.calls: list[tuple[str, dict]] = []
        raw = envelope or {"found": False}
        entity = None
        if raw.get("found"):
            entity = EntityData(
                id=raw["id"], type=raw["type"], properties=raw["properties"],
                labels=raw.get("labels", []),
            )
        self._envelope = ToolResult(data=EntityLookupData(
            found=bool(raw.get("found")), entity_id=raw.get("id", ""), entity=entity,
        ))

    def __call__(self, tool_name: str, **kwargs: Any) -> Any:
        self.calls.append((tool_name, kwargs))
        if tool_name != "graph_graph_get_target_app":
            raise AssertionError(f"unexpected tool: {tool_name}")
        return self._envelope


class TestBuildTargetProfileDelegation:
    def test_invokes_typed_target_app(self) -> None:
        inv = _Invoker({
            "found": True, "id": "app-x", "type": "TargetApp",
            "properties": {
                "name": "WebGoat", "app_type": "web_application",
                "framework": "Spring", "ports": "8080,8443",
                "tech_stack": "Java,Spring", "endpoints_total": 42,
                "last_recon_run_id": "recon-r1",
            },
            "labels": ["TargetApp"],
        })
        profile = build_target_profile(inv, target_app="WebGoat", run_id="r1")

        tool_names = [c[0] for c in inv.calls]
        assert tool_names == ["graph_graph_get_target_app"]
        assert "graph_graph_query" not in tool_names

        target_call = inv.calls[0]
        assert target_call[1]["target_app"] == "WebGoat"
        assert target_call[1]["run_id"] == "r1"

        assert profile["app_name"] == "WebGoat"
        assert profile["framework"] == "Spring"
        assert profile["ports"] == ["8080", "8443"]
        assert profile["tech_stack"] == ["Java", "Spring"]
        assert profile["endpoints_total"] == 42
        assert profile["last_recon_run_id"] == "recon-r1"

    def test_returns_empty_profile_when_not_found(self) -> None:
        inv = _Invoker()
        profile = build_target_profile(inv, target_app="ghost", run_id="r1")
        assert profile["app_name"] == "ghost"
        assert profile["app_type"] == "unknown"
        assert profile["tech_stack"] == []
        assert profile["ports"] == []

    def test_handles_invoker_exception_gracefully(self) -> None:
        def boom(_tool: str, **_kw: Any) -> Any:
            raise RuntimeError("graph offline")

        profile = build_target_profile(boom, target_app="WebGoat", run_id="r1")
        assert profile["app_name"] == "WebGoat"
        assert profile["app_type"] == "unknown"

    def test_no_cypher_in_target_source(self) -> None:
        path = pathlib.Path(
            "components/games/src/factory/games/runtime/workflow_report_target.py"
        )
        text = path.read_text(encoding="utf-8")
        assert "graph_graph_query" not in text
        assert "MATCH (" not in text
        assert "graph_graph_get_target_app" in text


class TestBuildTargetProfileProperties:
    @given(
        target_app=st.text(min_size=1, max_size=20),
        run_id=st.text(min_size=0, max_size=15,
                       alphabet=st.characters(whitelist_categories=("L", "N"))),
    )
    @settings(max_examples=25, deadline=None)
    def test_passes_args_through(
        self, target_app: str, run_id: str,
    ) -> None:
        inv = _Invoker()
        build_target_profile(inv, target_app=target_app, run_id=run_id)
        assert inv.calls[0][0] == "graph_graph_get_target_app"
        assert inv.calls[0][1]["target_app"] == target_app
        assert inv.calls[0][1]["run_id"] == run_id


def test_failed_tool_result_uses_empty_target_profile_fallback() -> None:
    inv = _Invoker()
    inv._envelope = ToolResult(ok=False, data=None, error="graph unavailable")
    profile = build_target_profile(inv, target_app="demo", run_id="run-failed")
    assert profile["app_name"] == "demo"
    assert profile["app_type"] == "unknown"