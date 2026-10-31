"""Framework-native cooperative steering behavior."""
from __future__ import annotations

from types import SimpleNamespace

import pytest

pytest.importorskip("langchain")

from factory.agent.runtime.adapters.langchain_steering import (
    LangChainSteeringMiddleware, SteerDelivery, SteeringContext, SteeringRuntime,
)
from factory.agent.runtime.adapters.session_completions import CompletionDelivery
from factory.agent.runtime.runtime_contracts import RuntimeInvocation


def _request() -> RuntimeInvocation:
    return RuntimeInvocation(
        invocation_id="run-1", agent_id="companion-x-default", prompt="start",
        capability_scope_digest="scope", thread_id="thread-1",
        tenant_id="tenant-1", owner_id="owner-1",
    )


class RecordingPort:
    def __init__(self, deliveries: tuple[SteerDelivery, ...] = ()) -> None:
        self.deliveries = deliveries
        self.consumed: list[str] = []
        self.requeued: list[str] = []
        self.completions: tuple[CompletionDelivery, ...] = ()
        self.acknowledged: list[str] = []
        self.ensured = 0

    def ensure(self, request: RuntimeInvocation) -> str | None:
        assert request == _request()
        self.ensured += 1
        return "session-1"

    def written(self, request: RuntimeInvocation) -> tuple[SteerDelivery, ...]:
        assert request == _request()
        return self.deliveries

    def consume(self, delivery: SteerDelivery) -> bool:
        self.consumed.append(delivery.delivery_id)
        return True

    def pending_completions(self, request: RuntimeInvocation):
        assert request == _request()
        return self.completions

    def acknowledge_completion(self, delivery: CompletionDelivery) -> bool:
        self.acknowledged.append(delivery.run_id)
        return True

    def requeue_written(self, request: RuntimeInvocation) -> tuple[str, ...]:
        assert request == _request()
        self.requeued.extend(item.delivery_id for item in self.deliveries)
        return tuple(self.requeued)


@pytest.mark.asyncio
async def test_boundary_injects_then_acknowledges_only_after_model() -> None:
    delivery = SteerDelivery(
        tenant_id="tenant-1", owner_id="owner-1", session_id="session-1",
        delivery_id="delivery-1", send_id="send-1", content="change direction",
        revision=1,
    )
    port = RecordingPort((delivery,))
    middleware = LangChainSteeringMiddleware(port)
    context = SteeringContext(_request())
    runtime = SimpleNamespace(context=context)

    update = await middleware.abefore_model({}, runtime)
    assert [message.content for message in update["messages"]] == ["change direction"]
    assert update["messages"][0].id == "send-1"
    assert port.consumed == []
    await middleware.aafter_model({}, runtime)
    assert port.consumed == ["delivery-1"]
    assert context.injected == []


@pytest.mark.asyncio
async def test_completion_reaches_origin_model_boundary_then_acknowledges() -> None:
    completion = CompletionDelivery(
        tenant_id="tenant-1", owner_id="owner-1", session_id="session-1",
        run_id="run:background", outcome="ok", summary="finished safely",
        result_digest="a" * 64, revision=1,
    )
    port = RecordingPort()
    port.completions = (completion,)
    middleware = LangChainSteeringMiddleware(port)
    context = SteeringContext(_request())
    runtime = SimpleNamespace(context=context)
    update = await middleware.abefore_model({}, runtime)
    assert update["messages"][0].content == (
        "[Subagent completion event]\nRun run:background: ok.\nfinished safely"
    )
    assert port.acknowledged == []
    await middleware.aafter_model({}, runtime)
    assert port.acknowledged == ["run:background"]
    assert context.completions == []


@pytest.mark.asyncio
async def test_turn_finally_requeues_only_still_written_deliveries() -> None:
    delivery = SteerDelivery(
        tenant_id="tenant-1", owner_id="owner-1", session_id="session-1",
        delivery_id="delivery-2", send_id="send-2", content="too late", revision=1,
    )
    port = RecordingPort((delivery,))
    steering = SteeringRuntime(port)
    with pytest.raises(RuntimeError, match="turn failed"):
        async with steering.turn(_request()):
            raise RuntimeError("turn failed")
    assert port.requeued == ["delivery-2"]


@pytest.mark.asyncio
async def test_anonymous_turn_never_reads_or_settles_mailbox() -> None:
    request = RuntimeInvocation(
        invocation_id="anon", agent_id="companion-x-default",
        prompt="hello", capability_scope_digest="scope", thread_id="thread-1",
    )
    port = RecordingPort()
    steering = SteeringRuntime(port)
    async with steering.turn(request) as context:
        runtime = SimpleNamespace(context=context)
        assert await steering.middleware.abefore_model({}, runtime) is None
    assert port.consumed == [] and port.requeued == []


@pytest.mark.asyncio
async def test_requeue_failure_does_not_mask_original_turn_error(caplog) -> None:
    class FailingPort(RecordingPort):
        def requeue_written(self, request):
            raise RuntimeError("mailbox unavailable")

    steering = SteeringRuntime(FailingPort())
    with pytest.raises(ValueError, match="original failure"):
        async with steering.turn(_request()):
            raise ValueError("original failure")
    assert "steer requeue failed after turn error" in caplog.text


@pytest.mark.asyncio
async def test_terminal_consume_race_is_benign_and_not_duplicated() -> None:
    delivery = SteerDelivery(
        tenant_id="tenant-1", owner_id="owner-1", session_id="session-1",
        delivery_id="delivery-race", send_id="send-race", content="seen", revision=1,
    )

    class TerminalWinnerPort(RecordingPort):
        def consume(self, item):
            return False

        def requeue_written(self, request):
            return ()

    port = TerminalWinnerPort((delivery,))
    context = SteeringContext(_request())
    runtime = SimpleNamespace(context=context)
    middleware = LangChainSteeringMiddleware(port)
    assert await middleware.abefore_model({}, runtime) is not None
    await middleware.aafter_model({}, runtime)
    assert context.injected == []
    async with SteeringRuntime(port).turn(_request()):
        pass
    assert port.requeued == []


@pytest.mark.asyncio
async def test_offer_writes_only_while_verified_turn_is_active() -> None:
    delivery = SteerDelivery(
        tenant_id="tenant-1", owner_id="owner-1", session_id="session-1",
        delivery_id="delivery-offer", send_id="send-offer", content="redirect",
        revision=1,
    )

    class OfferPort(RecordingPort):
        writes: list[str] = []

        def write(self, request, send_id, content):
            self.writes.append(send_id)
            return delivery

    port = OfferPort()
    steering = SteeringRuntime(port)
    async with steering.turn(_request()):
        offered = await steering.offer(_request(), "send-offer", "redirect")
        assert offered == delivery
    assert port.writes == ["send-offer"]
    assert await steering.offer(_request(), "send-late", "late") is None
    assert port.writes == ["send-offer"]
