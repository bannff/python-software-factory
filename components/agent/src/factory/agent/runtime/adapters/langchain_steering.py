"""Cooperative steering at LangChain model boundaries."""
from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
import logging
from typing import TYPE_CHECKING, Any, Protocol

from ..runtime_contracts import RuntimeInvocation

if TYPE_CHECKING:
    # Dormant laziness: langchain imports live in the langgraph-legacy group.
    from langchain.agents.middleware import AgentMiddleware  # noqa: F401

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class SteerDelivery:
    tenant_id: str
    owner_id: str
    session_id: str
    delivery_id: str
    send_id: str
    content: str
    revision: int


class SteeringPort(Protocol):
    def ensure(self, request: RuntimeInvocation) -> str | None: ...
    def write(self, request: RuntimeInvocation, send_id: str, content: str) -> SteerDelivery: ...
    def written(self, request: RuntimeInvocation) -> tuple[SteerDelivery, ...]: ...
    def consume(self, delivery: SteerDelivery) -> bool: ...
    def requeue_written(self, request: RuntimeInvocation) -> tuple[str, ...]: ...


@dataclass
class SteeringContext:
    request: RuntimeInvocation
    injected: list[SteerDelivery] = field(default_factory=list)
    completions: list[Any] = field(default_factory=list)
    lessons_injected: bool = False
    lesson_ids: list[str] = field(default_factory=list)
    hybrid_recall_injected: bool = False
    hybrid_node_ids: list[str] = field(default_factory=list)


class NullSteeringPort:
    def ensure(self, request: RuntimeInvocation) -> str | None:
        return None

    def write(self, request: RuntimeInvocation, send_id: str, content: str) -> SteerDelivery:
        raise RuntimeError("steering is unavailable")

    def written(self, request: RuntimeInvocation) -> tuple[SteerDelivery, ...]:
        return ()

    def consume(self, delivery: SteerDelivery) -> bool:
        return False

    def requeue_written(self, request: RuntimeInvocation) -> tuple[str, ...]:
        return ()


try:
    # Real base with the langgraph-legacy group; object keeps group-less alive.
    from langchain.agents.middleware import AgentMiddleware as _MiddlewareBase
except ImportError:  # pragma: no cover - exercised only without the group
    _MiddlewareBase = object  # type: ignore[misc,assignment]


def _human_message(content: str, message_id: str | None) -> Any:
    from langchain_core.messages import HumanMessage

    return HumanMessage(content=content, id=message_id)


class LangChainSteeringMiddleware(_MiddlewareBase):
    """Inject written steers before a model and settle only after it returns."""

    def __init__(self, port: SteeringPort) -> None:
        self._port = port

    async def abefore_model(self, state: Any, runtime: Any) -> dict[str, Any] | None:
        del state
        context: SteeringContext = runtime.context
        request = context.request
        if request.tenant_id is None:
            return None
        deliveries = self._port.written(request)
        pending = getattr(self._port, "pending_completions", lambda _request: ())
        completions = pending(request)
        if not deliveries and not completions:
            return None
        context.injected.extend(deliveries)
        context.completions.extend(completions)
        messages = [
            _human_message(item.content, item.send_id) for item in deliveries
        ]
        messages.extend(_human_message(
            f"[Subagent completion event]\nRun {item.run_id}: "
            f"{item.outcome}.\n{item.summary}",
            f"completion-{item.run_id}",
        ) for item in completions)
        return {"messages": messages}

    async def aafter_model(self, state: Any, runtime: Any) -> None:
        del state
        context: SteeringContext = runtime.context
        for delivery in tuple(context.injected):
            self._port.consume(delivery)
            context.injected.remove(delivery)
        acknowledge = getattr(self._port, "acknowledge_completion", lambda _item: False)
        for completion in tuple(context.completions):
            if acknowledge(completion):
                context.completions.remove(completion)


class SteeringRuntime:
    """Race-fence active-turn writes against durable turn-final requeue."""

    def __init__(self, port: SteeringPort | None = None) -> None:
        self.port = port or NullSteeringPort()
        self.middleware = LangChainSteeringMiddleware(self.port)
        self._active: set[tuple[str, str, str, str]] = set()
        self._lock = asyncio.Lock()

    async def offer(
        self, request: RuntimeInvocation, send_id: str, content: str,
    ) -> SteerDelivery | None:
        if request.tenant_id is None or request.thread_id is None:
            return None
        async with self._lock:
            if self._key(request) not in self._active:
                return None
            return self.port.write(request, send_id, content)

    @asynccontextmanager
    async def turn(
        self, request: RuntimeInvocation,
    ) -> AsyncIterator[SteeringContext]:
        identified = request.tenant_id is not None and request.thread_id is not None
        if identified:
            # `ensure` is a synchronous call that blocks on a nested
            # `asyncio.run` (native tool invocation via the agent pool).
            # Calling it bare here — inside this async generator's frame,
            # which is itself running as a task on the graph turn's event
            # loop — nests a second, independent event loop underneath the
            # first without ever yielding control back to the outer loop.
            # anyio's cancel-scope bookkeeping is keyed to the task that
            # entered a scope; a checkpoint/cancellation crossing the outer
            # task while this frame is parked inside the inner loop raises
            # "Attempted to exit cancel scope in a different task than it
            # was entered in" once the graph proceeds. Running it via
            # `asyncio.to_thread` keeps the blocking work on a plain worker
            # thread and lets the outer loop's task machinery track the
            # await properly, instead of doing hidden sync I/O in an async
            # frame.
            await asyncio.to_thread(self.port.ensure, request)
            async with self._lock:
                self._active.add(self._key(request))
        try:
            yield SteeringContext(request)
        except BaseException:
            await self._finish(request, preserve_error=True)
            raise
        else:
            await self._finish(request, preserve_error=False)

    async def _finish(self, request: RuntimeInvocation, preserve_error: bool) -> None:
        if request.tenant_id is None or request.thread_id is None:
            return
        async with self._lock:
            try:
                # Same nested-loop hazard as `ensure` above — keep this off
                # the graph turn's own task/loop.
                await asyncio.to_thread(self.port.requeue_written, request)
            except Exception:
                if not preserve_error:
                    raise
                logger.exception(
                    "steer requeue failed after turn error invocation_id=%s",
                    request.invocation_id,
                )
            finally:
                self._active.discard(self._key(request))

    @staticmethod
    def _key(request: RuntimeInvocation) -> tuple[str, str, str, str]:
        assert request.tenant_id and request.owner_id and request.thread_id
        return request.tenant_id, request.owner_id, request.agent_id, request.thread_id


__all__ = [
    "LangChainSteeringMiddleware", "NullSteeringPort", "SteerDelivery",
    "SteeringContext", "SteeringPort", "SteeringRuntime",
]
