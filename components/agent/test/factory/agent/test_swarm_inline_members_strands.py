"""Registered swarms execute on the strands adapter with inline members (#442)."""
from __future__ import annotations

from typing import Any

import pytest

pytest.importorskip("strands")

from factory.agent.runtime import coordination
from factory.agent.runtime.adapters.strands_multiagent_graph import (
    StrandsMultiagentGraphExecutor,
)

from ._strands_graph_fakes import GraphReplyModel
from ._swarm_member_fakes import (
    CODE_REVIEW, PERMISSIONS_DIR, capability_client, swarm_config,
)


class RecordingModel(GraphReplyModel):
    """Shared echo fake that also records system prompt and offered tool specs."""

    def __init__(self, sink: list[dict[str, Any]]) -> None:
        super().__init__()
        self._sink = sink

    async def stream(self, messages: Any, tool_specs: Any = None,
                     system_prompt: Any = None, **kwargs: Any):
        self._sink.append({
            "system": system_prompt,
            "tools": sorted(spec["name"] for spec in tool_specs or ()),
        })
        async for event in super().stream(messages, tool_specs, system_prompt, **kwargs):
            yield event


class _Agents:
    _model_id = "fake"
    client = capability_client()
    capability_scope_digest = client.scope.digest


class _Pair:
    def __init__(self, sink: list[dict[str, Any]]) -> None:
        self.executor = StrandsMultiagentGraphExecutor(
            _Agents(), model_builder=lambda _mid, **_kw: RecordingModel(sink),
        )

    async def invoke_graph(self, request: Any) -> Any:
        return await self.executor.invoke_graph(request)

    async def close(self) -> None:
        return None


@pytest.fixture
def calls(monkeypatch: pytest.MonkeyPatch) -> list[dict[str, Any]]:
    monkeypatch.setenv("MCP_PERMISSIONS_CONFIG_DIR", PERMISSIONS_DIR)
    sink: list[dict[str, Any]] = []
    monkeypatch.setattr(
        "factory.agent.runtime.adapters.create_runtime_pair",
        lambda: (_Agents(), _Pair(sink)),
    )
    return sink


@pytest.mark.asyncio
async def test_registered_code_review_swarm_runs_each_member_with_own_scope(
    calls: list[dict[str, Any]],
) -> None:
    result = await coordination.execute_registered(CODE_REVIEW, "review it", {})
    assert result["status"] == "completed", result
    assert result["execution_order"] == ("static-analyzer", "dependency-checker")
    for agent, call in zip(CODE_REVIEW.agents, calls, strict=True):
        assert agent.system_prompt in call["system"]
    # The base authority also holds devtools_write_file; members never get it.
    assert all(c["tools"] == ["devtools_list_dir", "devtools_read_file"] for c in calls)


@pytest.mark.asyncio
async def test_same_member_id_in_two_swarms_keeps_its_own_definition(
    calls: list[dict[str, Any]],
) -> None:
    for sid, prompt, tool in (("s1", "You write report one.", "devtools_read_file"),
                              ("s2", "You write report two.", "devtools_list_dir")):
        await coordination.execute_registered(
            swarm_config(prompt, [tool], swarm_id=sid), "t", {})
    seen = [(c["tools"], "report one" in c["system"], "report two" in c["system"])
            for c in calls]
    assert seen == [(["devtools_read_file"], True, False),
                    (["devtools_list_dir"], False, True)]
