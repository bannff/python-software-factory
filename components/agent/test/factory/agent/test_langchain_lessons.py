from __future__ import annotations

from types import SimpleNamespace

import pytest
pytest.importorskip("langchain")
pytest.importorskip("langgraph")
pytest.importorskip("langchain_community")

from factory.agent.runtime.adapters.langchain_lessons import LangChainLessonsMiddleware
from factory.agent.runtime.adapters.langchain_steering import SteeringContext
from factory.agent.runtime.runtime_contracts import RuntimeInvocation


def _request() -> RuntimeInvocation:
    return RuntimeInvocation(
        invocation_id="run-1", agent_id="developer", prompt="help",
        capability_scope_digest="scope", thread_id="thread",
        tenant_id="tenant", owner_id="owner",
    )


class Port:
    def __init__(self):
        self.applied_ids = []
        self.calls = 0

    async def recall(self, request):
        self.calls += 1
        return [{
            "lesson_id": "les_" + "a" * 32,
            "rule": "Always cite exact evidence",
            "negative": "Never invent a source",
        }]

    async def applied(self, request, lesson_ids):
        self.applied_ids.append(tuple(lesson_ids))


@pytest.mark.asyncio
async def test_lessons_inject_once_before_model_and_emit_ids_only() -> None:
    port = Port()
    middleware = LangChainLessonsMiddleware(port)
    context = SteeringContext(_request())
    runtime = SimpleNamespace(context=context)
    update = await middleware.abefore_model({}, runtime)
    text = update["messages"][0].content
    assert "Always cite exact evidence" in text
    assert "Never invent a source" in text
    assert "higher-priority policy wins" in text
    assert await middleware.abefore_model({}, runtime) is None
    assert port.calls == 1
    assert port.applied_ids == [("les_" + "a" * 32,)]
    assert context.lesson_ids == ["les_" + "a" * 32]


@pytest.mark.asyncio
async def test_anonymous_turn_never_queries_lessons() -> None:
    request = RuntimeInvocation(
        invocation_id="anon", agent_id="developer", prompt="help",
        capability_scope_digest="scope",
    )
    port = Port()
    update = await LangChainLessonsMiddleware(port).abefore_model(
        {}, SimpleNamespace(context=SteeringContext(request)),
    )
    assert update is None and port.calls == 0


@pytest.mark.asyncio
async def test_unavailable_recall_does_not_break_existing_chat(caplog) -> None:
    class FailingPort:
        async def recall(self, request):
            raise RuntimeError("lessons offline")

    context = SteeringContext(_request())
    update = await LangChainLessonsMiddleware(FailingPort()).abefore_model(
        {}, SimpleNamespace(context=context),
    )
    assert update is None
    assert context.lessons_injected
    assert "lesson recall unavailable" in caplog.text
