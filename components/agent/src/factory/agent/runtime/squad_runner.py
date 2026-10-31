"""Assemble a deployable squad — part (c) of the squad runner (issue #763).

``prepare_squad`` turns a ``SquadConfig`` into a ready-to-run bundle: it
validates the local toolbelt, builds the LOCAL tools bound to the container
workspace, and opens or binds a bearer-free per-launch proxy MCP client.
``run_squad`` then binds the local toolbelt onto the LangGraph
runtime and executes the embedded team. This module owns resolution
(``prepare_squad``), the safety preconditions, and execution (``run_squad``).

Guardrails enforced here (carried from the part-(a) gate):
- ``toolbelt.tools`` must be known local tools (``available_local_tools``) —
  typos fail loud, not silently no-op.
- ``shell`` is bound only when ``allow_shell`` is true. The deploy composition
  sets this from the container-isolation precondition (no host secret mounts,
  only the scoped phone-home egress); an untrusted target + shell + shared
  secret is an escape, so this fails loud when isolation is not asserted.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from uuid import uuid4

from .adapters.local_toolbelt import available_local_tools, build_local_toolbelt
from .runtime_contracts import GraphEdge, GraphNode, GraphRequest, RuntimeInvocation
from .squad_contracts import SquadConfig


@dataclass
class PreparedSquad:
    """A resolved squad ready for execution binding."""

    config: SquadConfig
    workspace: Path
    local_tools: list[Any]
    capability_client: Any | None  # ScopedCapabilityClientPort | None

    async def aclose(self) -> None:
        """Release the phone-home session, if one was opened."""
        if self.capability_client is not None:
            await self.capability_client.close()


def _validate_toolbelt(config: SquadConfig) -> None:
    known = set(available_local_tools())
    unknown = [name for name in config.toolbelt.tools if name not in known]
    if unknown:
        raise ValueError(
            f"squad {config.id!r} requests unknown local tools {unknown}; "
            f"available: {sorted(known)}"
        )


async def prepare_squad(
    config: SquadConfig, *, workspace: str | Path,
    mcp_url: str | None = None, capability_client: Any | None = None,
    capability_policy_id: str | None = None, proxy_socket: str | None = None,
    allow_shell: bool = True,
) -> PreparedSquad:
    """Resolve a squad into local tools + an optional phone-home client.

    ``mcp_url`` is only a bearer-free per-launch proxy MCP endpoint. It must
    never identify the upstream Companion-X gateway. ``proxy_socket`` (when the
    host bind-mounts a per-launch Unix socket) dials that socket instead of TCP
    — no bearer ever enters the container.
    ``allow_shell`` False → refuse to bind ``shell`` (isolation not asserted).
    """
    _validate_toolbelt(config)
    tool_names = list(config.toolbelt.tools)
    if "shell" in tool_names and not allow_shell:
        raise ValueError(
            f"squad {config.id!r} requests 'shell' but shell-binding is "
            "disabled; the container-isolation precondition is not asserted"
        )

    workspace_path = Path(workspace)
    local_tools = build_local_toolbelt(tool_names, workspace_path)

    proxy_mcp_url = mcp_url or config.phone_home.mcp_url
    if proxy_mcp_url or capability_client is not None:
        allowlist = config.phone_home.tool_allowlist
        if not allowlist:
            raise ValueError("workload proxy requires a non-empty exact tool allowlist")
        scope = getattr(capability_client, "scope", None)
        if capability_client is None:
            if not capability_policy_id or not capability_policy_id.startswith("workload:"):
                raise ValueError("workload proxy requires the frozen launch policy id")
            if proxy_socket:
                from factory.mcp_utils.interface import open_uds_capability_client
                capability_client = await open_uds_capability_client(
                    proxy_mcp_url, proxy_socket, allowlist=allowlist,
                    policy_id=capability_policy_id,
                )
            else:
                from factory.mcp_utils.interface import open_http_capability_client
                capability_client = await open_http_capability_client(
                    proxy_mcp_url, allowlist=allowlist,
                    policy_id=capability_policy_id,
                )
        elif scope is None or scope.tool_names != frozenset(allowlist) \
                or not scope.policy_id.startswith("workload:") \
                or capability_policy_id not in (None, scope.policy_id):
            raise ValueError(
                "injected capability client must match the exact workload scope")
    return PreparedSquad(
        config=config, workspace=workspace_path,
        local_tools=local_tools, capability_client=capability_client,
    )


class _EmptyCapabilities:
    """Empty capability port for a local-only squad (no phone-home tools)."""

    def __init__(self) -> None:
        from factory.mcp_utils.interface import CapabilityScope
        self._scope = CapabilityScope.create("squad-local-only", [])

    @property
    def scope(self) -> Any:
        return self._scope

    async def list_capabilities(self) -> tuple:
        return ()

    async def invoke(self, request: Any) -> Any:  # pragma: no cover - never in scope
        from factory.mcp_utils.interface import CapabilityAccessError
        raise CapabilityAccessError("local-only squad has no remote capabilities")

    async def close(self) -> None:
        return None


def team_to_graph_request(
    config: SquadConfig, task: str, capability_scope_digest: str,
) -> GraphRequest:
    """Convert a squad's embedded team into an executable ``GraphRequest``.

    MVP supports a ``graph`` team of registered-persona agent nodes. Nested
    swarm/graph nodes and inline ``swarm`` teams raise (future sub-step).
    """
    team = config.team
    if team.kind != "graph":
        raise NotImplementedError(
            f"squad {config.id!r}: only 'graph' teams are runnable today, "
            f"got {team.kind!r}"
        )
    nodes: list[GraphNode] = []
    for node in team.nodes:
        if getattr(node, "type", None) != "agent":
            raise NotImplementedError(
                f"squad {config.id!r}: node {node.id!r} is {getattr(node, 'type', '?')!r}; "
                "only 'agent' nodes are runnable today"
            )
        nodes.append(GraphNode(node.id, node.agent_id or node.id))
    edges = [GraphEdge(edge.source, edge.target) for edge in team.edges]
    entry = nodes[0].agent_id if nodes else config.id
    return GraphRequest(
        invocation=RuntimeInvocation(
            invocation_id=uuid4().hex, agent_id=entry, prompt=task,
            capability_scope_digest=capability_scope_digest,
            model_id=config.model or "us.anthropic.claude-sonnet-4-6",
            memory_scope="default", thread_id=None,
            metadata={"squad_id": config.id},
        ),
        nodes=tuple(nodes), edges=tuple(edges),
        max_steps=min(2 * len(nodes), 64), timeout_seconds=1800.0,
    )

async def run_squad(prepared: PreparedSquad, task: str, *, model: Any = None) -> Any:
    """Run a prepared squad's team with its local toolbelt + phone-home tools.

    Builds the LangChain/LangGraph runtime with the local toolbelt bound to
    every node, then executes the embedded team. Returns the ``RuntimeResult``.
    Closing the graph closes the runtime + the phone-home session.
    """
    from .adapters.langchain_runtime import LangChainAgentRuntime
    from .adapters.langgraph_runtime import LangGraphRuntime
    from .adapters.langchain_model import build_langchain_chat_model
    model_id = prepared.config.model or "us.anthropic.claude-sonnet-4-6"
    model_builder = build_langchain_chat_model if model is None else None
    if model is None:
        model = build_langchain_chat_model(model_id)

    capabilities = prepared.capability_client or _EmptyCapabilities()
    runtime = LangChainAgentRuntime(
        model, capabilities, model_id=model_id, model_builder=model_builder,
        local_tools=prepared.local_tools,
    )
    graph = LangGraphRuntime(runtime)
    request = team_to_graph_request(
        prepared.config, task, runtime.capability_scope_digest)
    try:
        return await graph.invoke_graph(request)
    finally:
        await graph.close()  # closes runtime + phone-home capability session


__all__ = ["PreparedSquad", "prepare_squad", "run_squad", "team_to_graph_request"]
