"""Strands runtime factories for the agent/graph/coordination seams.

One ``StrandsAgentRuntime`` per attempt (mirrors the LangChain runtime's
attempt-local shape): scoped-capability client projected to native strands
tools, per-invocation approval store, and thread registry caching.
``StrandsGraphRuntime`` delegates declared DAGs to the real
``strands.multiagent.Graph`` executor (``strands_multiagent_graph``).
"""
from __future__ import annotations

import os
from collections.abc import AsyncIterator
from typing import Any

from factory.mcp_utils.interface import ScopedCapabilityClientPort

from ..approval_policy import ApprovalPolicyStore
from ..runtime_contracts import (
    GraphRequest as RuntimeRequest, RuntimeAdapterDescriptor,
    RuntimeInvocation, RuntimeLifecycleEvent, RuntimeResult,
)
from .strands_agent_factory import build_thread_agent_tools
from .strands_chat import StrandsChatAgent
from .strands_model import build_strands_model
from .strands_thread_registry import StrandsThreadRegistry


class StrandsAgentRuntime:
    """Attempt-local strands agent using only pre-scoped capabilities."""

    def __init__(
        self, client: ScopedCapabilityClientPort, *,
        model_id: str = "default",
        approval_store: ApprovalPolicyStore | None = None,
    ) -> None:
        self._client = client
        self._model_id = model_id
        self._approval_store = approval_store
        self._threads = StrandsThreadRegistry()

    @property
    def client(self) -> ScopedCapabilityClientPort:
        """The scoped capability client node agents build tools from."""
        return self._client

    async def invoke(self, request: RuntimeInvocation) -> RuntimeResult:
        agent = await self._agent_for(request)
        result = await agent.invoke_async(request.prompt)
        text = "".join(
            b["text"] for b in result.message.get("content", ())
            if isinstance(b, dict) and isinstance(b.get("text"), str)
        )
        return RuntimeResult(
            invocation_id=request.invocation_id, output=text,
            status="completed", metadata={},
        )

    async def _agent_for(self, request: RuntimeInvocation) -> Any:
        from ..personas import resolve_agent_config
        from ..steering_documents import apply_steering
        from strands import Agent

        persona = resolve_agent_config(request.agent_id)
        system_prompt, _digest = apply_steering(persona.system_prompt)

        async def build() -> Any:
            tools = await build_thread_agent_tools(self._client, persona)
            return Agent(
                agent_id=persona.id, name=f"{persona.id}-{request.thread_id}",
                system_prompt=system_prompt,
                model=build_strands_model(
                    request.model_id or self._model_id,
                    session_id=request.thread_id or "",
                ),
                tools=list(tools), callback_handler=None,
                hooks=[],
            )

        return await self._threads.get_or_build(
            request.thread_id or "", request.agent_id or "", build,
        )

    def descriptor(self) -> RuntimeAdapterDescriptor:
        return RuntimeAdapterDescriptor(
            adapter_id="strands", package_versions=(("strands-agents", "1.56.0"),),
        )

    async def aclose(self) -> None:
        await self._threads.aclose()


class StrandsGraphRuntime:
    """Bounded graph execution over the real ``strands.multiagent.Graph``."""

    def __init__(self, agents: StrandsAgentRuntime) -> None:
        from .strands_multiagent_graph import StrandsMultiagentGraphExecutor
        self._agents = agents
        self._executor = StrandsMultiagentGraphExecutor(agents)

    async def invoke_graph(self, request: RuntimeRequest) -> RuntimeResult:
        return await self._executor.invoke_graph(request)

    async def stream_graph(
        self, request: RuntimeRequest,
    ) -> AsyncIterator[RuntimeLifecycleEvent]:
        async for event in self._executor.stream_graph(request):
            yield event

    async def close(self) -> None:
        await self._agents.aclose()


def _default_approval_store() -> ApprovalPolicyStore:
    from .approval_policy_store import SqliteApprovalPolicyStore
    return SqliteApprovalPolicyStore(os.getenv(
        "COMPANION_X_APPROVAL_POLICY_DB_PATH", "./.storage/agent-approval.db",
    ))


__all__ = [
    "StrandsAgentRuntime", "StrandsGraphRuntime", "StrandsChatAgent",
    "_default_approval_store",
]