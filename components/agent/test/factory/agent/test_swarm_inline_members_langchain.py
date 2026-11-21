"""Registered swarms execute on the langchain adapter with inline members (#442)."""
from __future__ import annotations

from typing import Any

import pytest

pytest.importorskip("langchain")
pytest.importorskip("langgraph")

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from pydantic import Field

from factory.agent.runtime import coordination
from factory.agent.runtime.adapters import langchain_runtime as lc
from factory.agent.runtime.adapters.langgraph_runtime import LangGraphRuntime

from ._swarm_member_fakes import (
    CODE_REVIEW, PERMISSIONS_DIR, capability_client, swarm_config,
)


class RecordingModel(BaseChatModel):
    calls: list[dict[str, Any]] = Field(default_factory=list)
    offered: list[list[str]] = Field(default_factory=list)

    @property
    def _llm_type(self) -> str:
        return "swarm-member-fake"

    def bind_tools(self, tools: Any, **kwargs: Any) -> "RecordingModel":
        del kwargs
        self.offered.append(sorted(getattr(t, "name", None) or t["name"] for t in tools))
        return self

    def _generate(
        self, messages: list[Any], stop: Any = None, run_manager: Any = None,
        **kwargs: Any,
    ) -> ChatResult:
        del stop, run_manager, kwargs
        system = next(m.content for m in messages if m.type == "system")
        self.calls.append({"system": system, "tools": self.offered[-1]})
        return ChatResult(generations=[ChatGeneration(message=AIMessage(content="done"))])


@pytest.fixture
def model(monkeypatch: pytest.MonkeyPatch) -> RecordingModel:
    monkeypatch.setenv("MCP_PERMISSIONS_CONFIG_DIR", PERMISSIONS_DIR)
    recording = RecordingModel()

    def pair() -> tuple[Any, Any]:  # execute_registered closes what it is given
        agents = lc.LangChainAgentRuntime(recording, capability_client())
        return agents, LangGraphRuntime(agents)

    monkeypatch.setattr("factory.agent.runtime.adapters.create_runtime_pair", pair)
    return recording


@pytest.mark.asyncio
async def test_registered_code_review_swarm_runs_each_member_with_own_scope(
    model: RecordingModel,
) -> None:
    result = await coordination.execute_registered(CODE_REVIEW, "review it", {})
    assert result["status"] == "completed", result
    assert result["execution_order"] == ("static-analyzer", "dependency-checker")
    for agent, call in zip(CODE_REVIEW.agents, model.calls, strict=True):
        assert agent.system_prompt in call["system"]
    # The base authority also holds devtools_write_file; members never get it.
    assert all(call["tools"] == ["devtools_list_dir", "devtools_read_file"]
               for call in model.calls)


@pytest.mark.asyncio
async def test_same_member_id_in_two_swarms_keeps_its_own_definition(
    model: RecordingModel,
) -> None:
    one = swarm_config("You write report one.", ["devtools_read_file"], swarm_id="s1")
    two = swarm_config("You write report two.", ["devtools_list_dir"], swarm_id="s2")
    await coordination.execute_registered(one, "t", {})
    await coordination.execute_registered(two, "t", {})
    seen = [(c["tools"], "report one" in c["system"], "report two" in c["system"])
            for c in model.calls]
    assert seen == [(["devtools_read_file"], True, False),
                    (["devtools_list_dir"], False, True)]
