"""Framework-neutral Protocol ports for bounded Agent runtime adapters.

Extracted from ``runtime_contracts.py`` (LOC ceiling) — the Protocol
definitions are structurally separate from the dataclass contracts they
reference, so this split follows the same doctrine as every other
LOC-driven extraction in this session (``bulk_delete_support.py``,
``memory_filters.py``, etc.).
"""
from __future__ import annotations

from typing import AsyncIterator, Protocol, runtime_checkable

from .runtime_contracts import (
    GraphRequest, RuntimeInvocation, RuntimeLifecycleEvent, RuntimeResult,
    RuntimeAdapterDescriptor,
)


@runtime_checkable
class AgentRuntimePort(Protocol):
    """Private adapter port; SDK objects never cross this boundary."""

    @property
    def descriptor(self) -> RuntimeAdapterDescriptor:
        """Return the trusted adapter identity fixed at startup."""
        ...

    async def invoke(self, request: RuntimeInvocation) -> RuntimeResult:
        """Run one bounded invocation to a terminal result."""
        ...

    async def stream(
        self, request: RuntimeInvocation,
    ) -> AsyncIterator[RuntimeLifecycleEvent]:
        """Stream normalized events for one bounded invocation."""
        ...

    async def cancel(self, invocation_id: str) -> None:
        """Request cancellation without changing Workflow ownership."""
        ...

    async def cancel_thread(self, thread_id: str) -> bool:
        """Cancel every live invocation for a thread; True if any were live."""
        ...

    async def close(self) -> None:
        """Release adapter-owned attempt-local resources."""
        ...


@runtime_checkable
class GraphRuntimePort(Protocol):
    """Private adapter port for declared, bounded LangGraph execution."""

    async def invoke_graph(self, request: GraphRequest) -> RuntimeResult:
        """Run one declared graph without acquiring durable ownership."""
        ...

    async def stream_graph(
        self, request: GraphRequest,
    ) -> AsyncIterator[RuntimeLifecycleEvent]:
        """Stream normalized events for one declared graph."""
        ...


__all__ = ["AgentRuntimePort", "GraphRuntimePort"]
