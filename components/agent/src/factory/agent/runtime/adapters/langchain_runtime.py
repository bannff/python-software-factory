"""Exact LangChain 1.3.17 AgentRuntimePort adapter."""
from __future__ import annotations

import asyncio
import os
from collections.abc import AsyncIterator
from importlib.metadata import version
from typing import Any
from factory.mcp_utils.interface import ScopedCapabilityClientPort
from ..approval_policy import ApprovalPolicyStore, InMemoryApprovalPolicyStore
from ..runtime_contracts import (
    RuntimeAdapterDescriptor, RuntimeInvocation, RuntimeLifecycleEvent, RuntimeResult,
)
from .langchain_active_threads import ActiveThreadRegistry, cancel_and_drain
from .langchain_checkpoints import AsyncSqliteCheckpoints
from .langchain_graph_cache import CompiledGraphCache
from .langchain_invocation_stream import invocation_stream
from .langchain_models import LangChainModelCache, ModelBuilder
from .langchain_steering import SteeringPort, SteeringRuntime
from .langchain_stream import (
    ToolChunkState,
    graph_input,
    last_assistant_text,
    message_events,
    pending_interrupt_events,
)
from .langchain_thread_history import (
    capture_branch_id, checkpoint_before_message, fork_thread, history,
)
from .langchain_tools import bind_invocation, reset_invocation
_REQUIRED = (("langchain", "1.3.17"), ("langgraph", "1.2.11"))
class LangChainAgentRuntime:
    """Attempt-local LangChain agent using only pre-scoped capabilities."""

    def __init__(
        self, model: Any, capabilities: ScopedCapabilityClientPort, *,
        model_id: str = "default", model_builder: ModelBuilder | None = None,
        local_tools: list[Any] | None = None,
        checkpoint_path: str | os.PathLike[str] = ":memory:",
        steering: SteeringPort | None = None,
        approval_store: ApprovalPolicyStore | None = None,
    ) -> None:
        installed = tuple((name, version(name)) for name, _ in _REQUIRED)
        if installed != _REQUIRED:
            raise RuntimeError(f"Lang runtime version mismatch: {installed!r}")
        self._models = LangChainModelCache(model, model_id, model_builder)
        self._capabilities = capabilities
        self._local_tools = list(local_tools or [])
        self._checkpoints = AsyncSqliteCheckpoints(checkpoint_path)
        self._steering = SteeringRuntime(steering)
        self._approval_store = approval_store or InMemoryApprovalPolicyStore()
        from .langchain_recall import build_recall_middleware
        self._recall_middleware = build_recall_middleware()
        self._graph_cache = CompiledGraphCache(
            capabilities, self._approval_store, self._recall_middleware,
            self._steering, self._local_tools,
        )
        self._thread_keys: dict[str, set[str]] = {}
        self._active: dict[str, asyncio.Task[Any]] = {}
        self._active_threads = ActiveThreadRegistry()
        self._lock = asyncio.Lock()
        self._closed = False
    @property
    def descriptor(self) -> RuntimeAdapterDescriptor:
        return RuntimeAdapterDescriptor(
            adapter_id="langchain-langgraph",
            package_versions=_REQUIRED,
            features=frozenset({
                "bounded_graph", "chat", "frontend_interrupt_resume",
                "hybrid_recall", "per_session_models", "scoped_capabilities",
                "streaming",
            }),
        )
    @property
    def capability_scope_digest(self) -> str:
        return self._capabilities.scope.digest
    @property
    def capability_scope(self):
        """Return the trusted base scope for graph and spawn handoffs."""
        return self._capabilities.scope
    async def _graph(self, request: RuntimeInvocation) -> Any:
        self._require_open()
        checkpointer = await self._checkpoints.get()
        return await self._graph_cache.get(request, checkpointer, self._models)

    def _config(self, request: RuntimeInvocation) -> dict[str, Any]:
        if request.capability_scope_digest != self._capabilities.scope.digest:
            raise ValueError("capability scope digest mismatch")
        key = f"{request.agent_id}-{request.thread_id or request.invocation_id}"
        if request.thread_id:
            self._thread_keys.setdefault(request.thread_id, set()).add(key)
        configurable: dict[str, Any] = {"thread_id": key}
        if request.checkpoint_id:
            configurable["checkpoint_id"] = request.checkpoint_id  # row 16: pin to a named branch
        return {"configurable": configurable}
    async def history(self, agent_id: str, thread_id: str) -> list[dict[str, Any]]:
        return await history(self._checkpoints, agent_id, thread_id)

    async def fork_thread(self, agent_id: str, source_thread_id: str, target_thread_id: str) -> bool:
        return await fork_thread(self._checkpoints, agent_id, source_thread_id, target_thread_id)

    async def checkpoint_before_message(self, agent_id: str, thread_id: str, message_id: str) -> str | None:
        return await checkpoint_before_message(self._checkpoints, agent_id, thread_id, message_id)
    async def offer_steer(self, request: RuntimeInvocation, send_id: str, content: str) -> Any:
        return await self._steering.offer(request, send_id, content)
    async def invoke(self, request: RuntimeInvocation) -> RuntimeResult:
        graph = await self._graph(request)
        task = asyncio.current_task()
        if task is not None:
            self._active[request.invocation_id] = task
            self._active_threads.track(request.thread_id, request.invocation_id)
        token = bind_invocation(request)
        try:
            config = self._config(request)
            async with self._steering.turn(request) as context:
                state = await graph.ainvoke(
                    {"messages": [{"role": "user", "content": request.prompt}]},
                    config=config, context=context,
                )
            output = last_assistant_text(state.get("messages", ()))
            metadata: dict[str, Any] = {
                "agent_id": request.agent_id,
                "thread_id": request.thread_id or "",
            }
            structured = state.get("structured_response")
            if structured is not None:
                # M7.6 exit criterion #2 (feature-map): lift the real
                # structured value LangChain's own AgentState carries when
                # response_format was set -- this is the ONLY place it is
                # available; nothing downstream can reconstruct it from
                # plain text. JSON-safe so RuntimeResult.metadata stays a
                # plain dict at every layer above this one.
                metadata["structured_response"] = structured.model_dump(mode="json")
            if request.checkpoint_id:
                metadata["checkpoint_id"] = await capture_branch_id(graph, config["configurable"]["thread_id"])
            return RuntimeResult(request.invocation_id, output, "completed", metadata)
        except asyncio.CancelledError:
            return RuntimeResult(request.invocation_id, "", "cancelled")
        finally:
            reset_invocation(token)
            self._active.pop(request.invocation_id, None)
            self._active_threads.untrack(request.thread_id, request.invocation_id)
    async def stream(self, request: RuntimeInvocation) -> AsyncIterator[RuntimeLifecycleEvent]:
        graph = await self._graph(request)
        config = self._config(request)
        sequence = 0
        task = asyncio.current_task()
        if task is not None:
            self._active[request.invocation_id] = task
            self._active_threads.track(request.thread_id, request.invocation_id)
        try:
            async with self._steering.turn(request) as context:
                source = graph.astream(
                    await graph_input(graph, config, request), config=config,
                    context=context, stream_mode="messages")
                tool_chunks = ToolChunkState()
                async for message, _metadata in invocation_stream(source, request):
                    for kind, payload in message_events(message, tool_chunks):
                        sequence += 1
                        yield RuntimeLifecycleEvent(request.invocation_id, sequence, kind, payload)
                snapshot = await graph.aget_state(config)
                for kind, payload in pending_interrupt_events(snapshot):
                    sequence += 1
                    yield RuntimeLifecycleEvent(request.invocation_id, sequence, kind, payload)
            sequence += 1
            yield RuntimeLifecycleEvent(request.invocation_id, sequence, "done", {"reason": "stop"})
        finally:
            self._active.pop(request.invocation_id, None)
            self._active_threads.untrack(request.thread_id, request.invocation_id)
    def refresh_model(self, model_id: str, model: Any | None = None) -> None:
        """Replace one provider client and only graphs compiled against it."""
        self._require_open()
        self._models.replace(model_id, model)
        self._graph_cache.drop_model(model_id)
    async def cancel(self, invocation_id: str) -> None:
        task = self._active.get(invocation_id)
        if task is not None and task is not asyncio.current_task():
            task.cancel()
    async def cancel_thread(self, thread_id: str) -> bool:
        """Cancel every live invocation for a thread; True if any were cancelled."""
        return self._active_threads.cancel_all(thread_id, self._active)
    def close_thread(self, thread_id: str) -> None:
        self._checkpoints.queue_delete(self._thread_keys.pop(thread_id, set()))
    async def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        await cancel_and_drain(self._active)
        self._graph_cache.clear()
        self._models.clear()
        await self._checkpoints.close()
        await self._capabilities.close()
    def _require_open(self) -> None:
        if self._closed:
            raise RuntimeError("LangChain runtime is closed")
__all__ = ["LangChainAgentRuntime"]
