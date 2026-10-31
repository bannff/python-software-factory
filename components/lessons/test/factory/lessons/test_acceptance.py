from __future__ import annotations

from types import SimpleNamespace

import pytest

from factory.agent.runtime.adapters.langchain_lessons import LangChainLessonsMiddleware
from factory.agent.runtime.adapters.langchain_steering import SteeringContext
from factory.agent.runtime.runtime_contracts import RuntimeInvocation
from factory.lessons.runtime.adapters.sql import SQLLessonStore
from factory.lessons.runtime.lifecycle import LessonLifecycle
from factory.lessons.runtime.projection import project_accepted
from factory.lessons.runtime.recall import recall
from factory.mcp_utils.interface import get_service, set_service
from factory.storage.interface import StorageRuntime


def _lifecycle(path) -> LessonLifecycle:
    sql = StorageRuntime().get_sql_store("sqlite", db_path=str(path))
    return LessonLifecycle(SQLLessonStore(sql))


def _response(data):
    return {"ok": True, "result": {"structured_content": {
        "ok": True, "data": data,
    }}}


@pytest.mark.asyncio
async def test_explicit_correction_changes_later_turn_after_restart(tmp_path) -> None:
    path = tmp_path / "lessons.db"
    lifecycle = _lifecycle(path)
    lesson = lifecycle.add(
        "tenant", "owner", "Always cite the exact source",
        negative="Never invent citations",
    ).lesson
    memories = []

    def factory(_caller):
        def invoke(target, **kwargs):
            args = kwargs["arguments"]
            if target["tool_name"] == "memory_store":
                item = {"id": "memory-1", "metadata": args["metadata"]}
                memories.append(item)
                return _response({"stored": True, "memory": item})
            if target["tool_name"] == "memory_retrieve":
                return _response({"memories": memories, "count": len(memories)})
            return _response({"event_id": "evt-applied"})
        return invoke

    previous = get_service("tool_invoker_for_caller")
    set_service("tool_invoker_for_caller", factory)
    try:
        assert await project_accepted(lifecycle.store) == (lesson.lesson_id,)
        restarted = _lifecycle(path)

        class Port:
            async def recall(self, request):
                values = await recall(
                    restarted.store, request.tenant_id, request.owner_id,
                    request.agent_id, request.prompt,
                )
                return [value.model_dump(mode="json") for value in values]

            async def applied(self, request, lesson_ids):
                return None

        request = RuntimeInvocation(
            invocation_id="later", agent_id="developer", prompt="answer with a citation",
            capability_scope_digest="scope", thread_id="thread",
            tenant_id="tenant", owner_id="owner",
        )
        update = await LangChainLessonsMiddleware(Port()).abefore_model(
            {}, SimpleNamespace(context=SteeringContext(request)),
        )
    finally:
        set_service("tool_invoker_for_caller", previous)
    learned_context = update["messages"][0].content
    baseline_response = "Here is an uncited answer."
    later_response = (
        "Answer with the exact source and no invented citation."
        if "Always cite the exact source" in learned_context
        else baseline_response
    )
    assert later_response != baseline_response
    assert "exact source" in later_response
