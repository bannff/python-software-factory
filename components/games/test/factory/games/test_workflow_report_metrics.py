"""Metrics-envelope coverage for Games experiment reporting."""
from __future__ import annotations

from typing import Any

from factory.games.runtime.workflow_report import _record_metrics
from factory.mcp_utils.interface import ToolResult


def test_record_metrics_uses_canonical_metrics_batch_name() -> None:
    calls: list[str] = []

    def invoker(name: str, **_kwargs: Any) -> ToolResult[object]:
        calls.append(name)
        if name != "metrics_record_batch":
            raise AssertionError(f"unexpected metrics tool: {name}")
        return ToolResult(data=object())

    _record_metrics(invoker, {"scoring": {"f1": 0.5}})
    assert calls == ["metrics_record_batch"]
