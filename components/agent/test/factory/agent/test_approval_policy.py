from pathlib import Path

import pytest
pytest.importorskip("langchain")
pytest.importorskip("langgraph")
pytest.importorskip("langchain_community")

from factory.agent.runtime.adapters.approval_policy_store import SqliteApprovalPolicyStore
from factory.agent.runtime.approval_policy import (
    ApprovalPolicy, InMemoryApprovalPolicyStore, StaleApprovalPolicy,
)


@pytest.mark.parametrize("names", [("x", "x"), ("",), ("bad\x00name",)])
def test_policy_rejects_invalid_tool_names(names: tuple[str, ...]) -> None:
    with pytest.raises(ValueError):
        ApprovalPolicy(tool_names=names)


def test_empty_default_preserves_autonomy() -> None:
    store = InMemoryApprovalPolicyStore()
    assert store.get("tenant", "owner") == ApprovalPolicy()


def test_in_memory_revision_cas() -> None:
    store = InMemoryApprovalPolicyStore()
    saved = store.update("tenant", "owner", 0, tool_names=("devtools_run_command",))
    assert saved.revision == 1
    with pytest.raises(StaleApprovalPolicy):
        store.update("tenant", "owner", 0, tool_names=())


def test_sqlite_restart_and_revision_cas(tmp_path: Path) -> None:
    path = tmp_path / "approval.db"
    first = SqliteApprovalPolicyStore(path)
    saved = first.update("tenant", "owner", 0, tool_names=("devtools_run_command",))
    assert SqliteApprovalPolicyStore(path).get("tenant", "owner") == saved
    with pytest.raises(StaleApprovalPolicy):
        first.update("tenant", "owner", 0, tool_names=())


@pytest.mark.asyncio
@pytest.mark.parametrize("approved,invocations", [(True, 1), (False, 0)])
async def test_listed_tool_interrupts_before_invocation(
    monkeypatch, approved: bool, invocations: int,
) -> None:
    from factory.agent.runtime.adapters.langchain_tools import (
        bind_invocation, build_langchain_tools, reset_invocation,
    )
    from factory.agent.runtime.runtime_contracts import RuntimeInvocation
    from factory.mcp_utils.interface import (
        CapabilityDescriptor, CapabilityResult, CapabilityScope,
    )
    from factory.mcp_utils.runtime.scoped_capability_client import (
        InMemoryScopedCapabilityClient,
    )
    import langgraph.types

    calls: list[int] = []
    scope = CapabilityScope.create("policy", {"demo_tool"})

    async def handler(_request):
        calls.append(1)
        return CapabilityResult(())

    client = InMemoryScopedCapabilityClient(
        scope,
        (CapabilityDescriptor("demo_tool", "demo", {"type": "object", "properties": {}}),),
        {"demo_tool": handler},
    )
    store = InMemoryApprovalPolicyStore()
    store.update("tenant", "owner", 0, tool_names=("demo_tool",))
    monkeypatch.setattr(langgraph.types, "interrupt", lambda _payload: {"approved": approved})
    tools = await build_langchain_tools(client, scope, store)
    token = bind_invocation(RuntimeInvocation(
        "run", "agent", "task", scope.digest,
        tenant_id="tenant", owner_id="owner",
    ))
    try:
        result = await tools[0].ainvoke({})
    finally:
        reset_invocation(token)
    assert len(calls) == invocations
    assert bool(result["is_error"]) is (not approved)


def test_pending_approval_event_uses_existing_interrupt_contract() -> None:
    from types import SimpleNamespace
    from factory.agent.runtime.adapters.langchain_stream import pending_approval_events

    snapshot = SimpleNamespace(interrupts=[SimpleNamespace(
        id="graph-id", value={"_approval_pending": True, "interrupt_id": "call-id",
                              "tool": "demo_tool", "command": "{}"})])
    assert pending_approval_events(snapshot) == [("interrupt", {
        "interrupt_id": "call-id", "tool": "demo_tool", "command": "{}",
    })]


@pytest.mark.asyncio
async def test_approval_policy_mcp_uses_ambient_identity() -> None:
    from factory.agent.mcp import approval_policy as approval_mcp
    from factory.mcp_utils.interface import ToolCatalog, reset_envelope, set_envelope

    store = InMemoryApprovalPolicyStore()
    catalog = ToolCatalog("approval-test")
    approval_mcp.register(catalog, store)
    tools = catalog.tool_map()
    token = set_envelope({"tenant_id": "tenant", "principal_id": "owner"})
    try:
        initial = tools["get_approval_policy"].fn()
        saved = tools["update_approval_policy"].fn(
            tool_names=["demo_tool"], expected_revision=0,
        )
        stale = tools["update_approval_policy"].fn(
            tool_names=[], expected_revision=0,
        )
    finally:
        reset_envelope(token)
    assert initial.ok and initial.data.revision == 0
    assert saved.ok and saved.data.tool_names == ["demo_tool"]
    assert not stale.ok and stale.error == "agent_approval_conflict"
    missing = tools["get_approval_policy"].fn()
    assert not missing.ok and missing.error == "agent_approval_unavailable"


@pytest.mark.asyncio
async def test_chat_adapter_exposes_typed_approval_interrupt() -> None:
    from factory.agent.runtime.adapters.langchain_chat import LangChainChatAgent
    from factory.agent.runtime.runtime_contracts import RuntimeLifecycleEvent

    class Runtime:
        capability_scope_digest = "scope"
        async def stream(self, request):
            yield RuntimeLifecycleEvent(request.invocation_id, 1, "interrupt", {
                "interrupt_id": "call-id", "tool": "demo_tool", "command": "{}",
            })

    events = [event async for event in LangChainChatAgent(Runtime()).stream(
        "thread", "do it", tenant_id="tenant", owner_id="owner",
    )]
    assert len(events) == 1 and events[0].type == "interrupt"
    assert events[0].interrupt_id == "call-id"


def test_correlation_carries_full_authority_payload() -> None:
    from factory.agent.runtime.adapters.langchain_tools import _correlation
    from factory.agent.runtime.runtime_contracts import RuntimeInvocation

    request = RuntimeInvocation(
        "inv-1", "agent-1", "task", "digest", thread_id="thread-1",
        tenant_id="tenant", owner_id="owner",
    )
    correlation = _correlation(request)
    assert correlation["invocation_id"] == "inv-1"
    assert correlation["agent_id"] == "agent-1"
    assert correlation["thread_id"] == "thread-1"
    assert correlation["tenant_id"] == "tenant"
    assert correlation["principal_id"] == "owner"


@pytest.mark.asyncio
async def test_update_approval_policy_rejects_unresolvable_tool_name() -> None:
    from factory.agent.mcp import approval_policy as approval_mcp
    from factory.mcp_utils.interface import ToolCatalog, set_envelope, reset_envelope

    store = InMemoryApprovalPolicyStore()
    catalog = ToolCatalog("approval-unknown-test")
    approval_mcp.register(catalog, store, resolve_names=lambda names: ())
    token = set_envelope({"tenant_id": "tenant", "principal_id": "owner"})
    try:
        out = catalog.tool_map()["update_approval_policy"].fn(
            tool_names=["not_a_real_tool"], expected_revision=0,
        )
    finally:
        reset_envelope(token)
    assert not out.ok and out.error == "agent_approval_unknown_tool"
    assert store.get("tenant", "owner").revision == 0
