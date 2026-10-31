"""Tests for squad assembly (prepare_squad) — local-only + guardrails."""
from __future__ import annotations

import pytest

for _mod in ("langchain", "langgraph", "langchain_community"):
    pytest.importorskip(_mod)

from factory.agent.runtime.squad_contracts import SquadConfig
from factory.agent.runtime.squad_runner import (
    prepare_squad, team_to_graph_request,
)


def _squad(tools, squad_id="rust-squad", allowlist=None) -> SquadConfig:
    return SquadConfig(
        id=squad_id, name="S", target_language="rust", sandbox_profile="rust-sdk",
        team={
            "kind": "graph", "id": "t", "name": "t",
            "nodes": [{"id": "e", "type": "agent", "agent_id": "developer"}],
            "entry_points": ["e"],
        },
        toolbelt={"tools": tools}, phone_home={"tool_allowlist": allowlist},
    )


@pytest.mark.asyncio
async def test_prepare_local_only_builds_toolbelt(tmp_path):
    squad = _squad(["shell", "write_file", "file_search"])
    prepared = await prepare_squad(squad, workspace=tmp_path)
    names = {t.name for t in prepared.local_tools}
    # framework tool names: ShellTool -> "terminal"; file tools keep their names
    assert names == {"terminal", "write_file", "file_search"}
    assert prepared.capability_client is None  # no mcp_url → no phone-home
    assert prepared.workspace == tmp_path
    await prepared.aclose()  # no-op when no client


@pytest.mark.asyncio
async def test_unknown_toolbelt_name_fails_loud(tmp_path):
    squad = _squad(["shell", "bogus_tool"])
    with pytest.raises(ValueError, match="unknown local tools"):
        await prepare_squad(squad, workspace=tmp_path)


@pytest.mark.asyncio
async def test_shell_gated_when_isolation_not_asserted(tmp_path):
    squad = _squad(["shell", "file_search"])
    with pytest.raises(ValueError, match="shell-binding is disabled"):
        await prepare_squad(squad, workspace=tmp_path, allow_shell=False)


@pytest.mark.asyncio
async def test_non_shell_squad_allowed_without_shell_permission(tmp_path):
    squad = _squad(["read_file", "file_search"])
    prepared = await prepare_squad(squad, workspace=tmp_path, allow_shell=False)
    assert {t.name for t in prepared.local_tools} == {"read_file", "file_search"}


@pytest.mark.asyncio
async def test_proxy_mcp_opens_bearer_free_exact_workload_scope(tmp_path, monkeypatch):
    from factory.mcp_utils.interface import CapabilityScope
    import factory.mcp_utils.interface as iface

    opened = {}

    class Client:
        scope = CapabilityScope.create(
            "workload:launch-1", ["graph_get_entity"])
        closed = False

        async def close(self):
            self.closed = True

    async def fake_open(url, *, allowlist, policy_id):
        opened.update(url=url, allowlist=allowlist, policy_id=policy_id)
        return Client()

    monkeypatch.setattr(iface, "open_http_capability_client", fake_open)
    squad = _squad(["file_search"], allowlist=["graph_get_entity"])
    prepared = await prepare_squad(
        squad, workspace=tmp_path, mcp_url="http://launch-proxy/mcp",
        capability_policy_id="workload:launch-1")
    assert opened == {
        "url": "http://launch-proxy/mcp",
        "allowlist": ["graph_get_entity"],
        "policy_id": "workload:launch-1",
    }
    await prepared.aclose()
    assert prepared.capability_client.closed

    injected = Client()
    prepared = await prepare_squad(
        squad, workspace=tmp_path, capability_client=injected)
    assert prepared.capability_client is injected


@pytest.mark.asyncio
async def test_proxy_socket_routes_to_uds_opener(tmp_path, monkeypatch):
    """A mounted socket dials the UDS opener, never the TCP one, no bearer."""
    from factory.mcp_utils.interface import CapabilityScope
    import factory.mcp_utils.interface as iface

    seen = {}

    class Client:
        scope = CapabilityScope.create("workload:launch-9", ["memory_store"])

        async def close(self):
            return None

    async def fake_uds(url, socket_path, *, allowlist, policy_id):
        seen.update(url=url, socket=socket_path, allowlist=allowlist, policy_id=policy_id)
        return Client()

    async def fail_http(*a, **k):  # must NOT be called on the socket path
        raise AssertionError("TCP opener used despite proxy_socket")

    monkeypatch.setattr(iface, "open_uds_capability_client", fake_uds)
    monkeypatch.setattr(iface, "open_http_capability_client", fail_http)
    squad = _squad(["file_search"], allowlist=["memory_store"])
    prepared = await prepare_squad(
        squad, workspace=tmp_path, mcp_url="http://localhost:80/mcp",
        proxy_socket="/run/companion-x/mcp.sock",
        capability_policy_id="workload:launch-9")
    assert seen == {
        "url": "http://localhost:80/mcp",
        "socket": "/run/companion-x/mcp.sock",
        "allowlist": ["memory_store"],
        "policy_id": "workload:launch-9",
    }
    await prepared.aclose()


def test_runner_has_no_raw_token_api() -> None:
    import inspect
    sig = inspect.signature(prepare_squad)
    assert "mcp_token" not in sig.parameters
    assert "proxy_socket" in sig.parameters


@pytest.mark.asyncio
async def test_remote_rejects_missing_allowlist(tmp_path):
    squad = _squad(["file_search"])
    with pytest.raises(ValueError, match="non-empty exact tool allowlist"):
        await prepare_squad(
            squad, workspace=tmp_path, mcp_url="http://proxy.invalid",
            capability_client=object())


def test_team_to_graph_request_maps_nodes_and_edges():
    squad = SquadConfig(
        id="rust-squad", name="S", sandbox_profile="rust-sdk",
        team={
            "kind": "graph", "id": "t", "name": "t",
            "nodes": [
                {"id": "editor", "type": "agent", "agent_id": "developer"},
                {"id": "reviewer", "type": "agent", "agent_id": "developer"},
            ],
            "edges": [{"source": "editor", "target": "reviewer"}],
            "entry_points": ["editor"],
        },
        toolbelt={"tools": ["shell"]},
    )
    req = team_to_graph_request(squad, "do the thing", "digest123")
    assert [n.node_id for n in req.nodes] == ["editor", "reviewer"]
    assert [n.agent_id for n in req.nodes] == ["developer", "developer"]
    assert [(e.source, e.target) for e in req.edges] == [("editor", "reviewer")]
    assert req.invocation.prompt == "do the thing"
    assert req.invocation.capability_scope_digest == "digest123"
    assert req.invocation.metadata["squad_id"] == "rust-squad"


def test_team_to_graph_request_rejects_swarm_team():
    squad = SquadConfig(
        id="sw", name="S", sandbox_profile="p",
        team={
            "kind": "swarm", "id": "s", "name": "s", "entry_point": "a",
            "agents": [
                {"id": "a", "model": "m", "system_prompt": "p"},
                {"id": "b", "model": "m", "system_prompt": "p"},
            ],
        },
        toolbelt={"tools": []},
    )
    with pytest.raises(NotImplementedError, match="only 'graph' teams"):
        team_to_graph_request(squad, "t", "d")


def test_runtime_seam_stores_local_tools():
    # The one production seam: LangChainAgentRuntime binds extra local tools.
    from factory.agent.runtime.adapters.langchain_runtime import LangChainAgentRuntime
    from factory.agent.runtime.squad_runner import _EmptyCapabilities

    sentinel = object()
    rt = LangChainAgentRuntime(object(), _EmptyCapabilities(), local_tools=[sentinel])
    assert rt._local_tools == [sentinel]
    # default remains empty → chat/existing graphs unchanged
    rt2 = LangChainAgentRuntime(object(), _EmptyCapabilities())
    assert rt2._local_tools == []
