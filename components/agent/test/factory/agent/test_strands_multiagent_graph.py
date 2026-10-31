"""Real ``strands.multiagent.Graph`` executor tests (issue #107).

Covers: 2-node linear DAG executes with ordered node output; fan-out/
fan-in diamond; node-cap overflow fails loudly pre-build; edge-condition
kinds that cannot map onto strands readiness fail loudly naming the kind;
result status mapping (completed / failed).
"""
from __future__ import annotations

from typing import Any

import pytest

pytest.importorskip("strands")

from factory.agent.runtime.adapters.strands_multiagent_graph import (
    StrandsMultiagentGraphExecutor,
)
from factory.agent.runtime.runtime_contracts import (
    GraphNode, GraphRequest, RuntimeInvocation,
)

from ._strands_graph_fakes import (
    FakeGraphAgents, GraphReplyModel, graph_request,
)


class _CondEdge:
    """GraphEdge stand-in carrying a declared condition string."""

    def __init__(self, source: str, target: str, *, condition: str) -> None:
        self.source = source
        self.target = target
        self.condition = condition


def _executor(**kwargs: Any) -> StrandsMultiagentGraphExecutor:
    from ._strands_graph_fakes import GraphReplyModel
    return StrandsMultiagentGraphExecutor(
        FakeGraphAgents(), model_builder=lambda _mid, **_kw: GraphReplyModel(), **kwargs,
    )


async def _collect(request: GraphRequest) -> list[Any]:
    return [event async for event in _executor().stream_graph(request)]


@pytest.mark.asyncio
async def test_two_node_linear_graph_runs_ordered() -> None:
    request = graph_request(
        [("a", "companion-x-default"), ("b", "eval-runner")],
        [("a", "b")],
    )
    result = await _executor().invoke_graph(request)
    assert result.status == "completed"
    events = await _collect(request)
    stops = [e for e in events if e.kind == "graph_node_completed"]
    assert [e.payload["node_id"] for e in stops] == ["a", "b"]
    outputs = result.metadata["node_outputs"]
    assert outputs["a"].startswith("reply:You are the Companion X assistant")
    assert outputs["b"].startswith("reply:You are an evaluation agent")
    assert outputs["a"] != outputs["b"]  # distinct personas → distinct output
    assert result.metadata["execution_order"] == ("a", "b")


@pytest.mark.asyncio
async def test_diamond_fan_out_fan_in() -> None:
    request = graph_request(
        [
            ("top", "companion-x-default"), ("left", "can-ingest"),
            ("right", "eval-runner"), ("bottom", "companion-x-default"),
        ],
        [("top", "left"), ("top", "right"), ("left", "bottom"), ("right", "bottom")],
    )
    result = await _executor().invoke_graph(request)
    assert result.status == "completed"
    events = await _collect(request)
    stops = [e.payload["node_id"] for e in events if e.kind == "graph_node_completed"]
    assert stops[0] == "top" and stops[-1] == "bottom"
    assert set(stops) == {"top", "left", "right", "bottom"}


@pytest.mark.asyncio
async def test_node_cap_overflow_fails_loudly() -> None:
    executor = StrandsMultiagentGraphExecutor(
        FakeGraphAgents(), max_nodes=2,
    )
    request = graph_request(
        [(n, "companion-x-default") for n in ("a", "b", "c")], [],
    )
    with pytest.raises(ValueError, match="exceeds cap"):
        await executor.invoke_graph(request)


@pytest.mark.asyncio
async def test_unmappable_edge_condition_raises_naming_kind() -> None:
    from dataclasses import replace

    base = graph_request(
        [("a", "companion-x-default"), ("b", "eval-runner")], [("a", "b")],
    )
    # Registry EdgeConfig carries a condition string; the neutral GraphEdge
    # contract doesn't, so simulate a declared condition via a same-shape edge.
    request = replace(
        base, edges=(_CondEdge("a", "b", condition="custom-predicate"),),
    )
    with pytest.raises(ValueError, match="custom-predicate"):
        await _executor().invoke_graph(request)


@pytest.mark.asyncio
async def test_failed_node_maps_to_failed_status() -> None:
    """A node whose agent raises mid-graph maps to failed status + event."""
    class ExplodingModel(GraphReplyModel):
        async def stream(self, messages: Any, tool_specs: Any = None,
                         system_prompt: Any = None, **kwargs: Any) -> AsyncIterator[dict]:
            raise RuntimeError("node exploded")
            yield  # pragma: no cover — makes this an async generator

    def exploding_builder(_mid: str, **_kw: Any) -> Any:
        return ExplodingModel()

    executor = StrandsMultiagentGraphExecutor(
        FakeGraphAgents(), model_builder=exploding_builder,
    )
    request = graph_request(
        [("a", "eval-runner"), ("b", "eval-runner")], [("a", "b")],
    )
    events = [e async for e in executor.stream_graph(request)]
    result = await executor.invoke_graph(request)
    assert result.status == "failed"
    failed = [e.payload["node_id"] for e in events if e.kind == "graph_node_failed"]
    assert failed == ["a"]


@pytest.mark.asyncio
async def test_unknown_edge_node_rejected_pre_build() -> None:
    request = graph_request(
        [("a", "companion-x-default")], [("a", "ghost")],
    )
    with pytest.raises(ValueError, match="unknown node"):
        await _executor().invoke_graph(request)
