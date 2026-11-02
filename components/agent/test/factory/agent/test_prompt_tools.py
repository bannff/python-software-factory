from __future__ import annotations

import asyncio

import pytest
from factory.mcp_utils.interface import reset_envelope, set_envelope

from factory.agent.mcp.contracts.prompts import PromptArgDTO
from factory.agent.mcp.prompt_tools import register


class _Mcp:
    def __init__(self) -> None:
        self.tools: dict = {}

    def tool(self):
        def deco(fn):
            self.tools[fn.__name__] = fn
            return fn
        return deco


class _Agent:
    def __init__(self, root) -> None:
        self.config_dir = str(root)


@pytest.fixture
def tools(tmp_path):
    mcp = _Mcp()
    register(mcp, _Agent(tmp_path))
    return mcp.tools


def _as(owner: str):
    return set_envelope({"tenant_id": "t", "principal_id": owner})


def test_crud_roundtrip_and_cas(tools) -> None:
    token = _as("alice")
    try:
        arg = PromptArgDTO(name="topic", description="what", required=True)
        added = tools["agent_add_prompt"](prompt_id="p1", template="Explain {topic}", arguments=[arg])
        assert added.ok and added.data.prompt.revision == 1
        assert tools["agent_add_prompt"](prompt_id="p1", template="x").error == "prompt_exists"
        stale = tools["agent_update_prompt"](prompt_id="p1", expected_revision=9, description="d")
        assert stale.error == "prompt_revision_conflict"
        upd = tools["agent_update_prompt"](prompt_id="p1", expected_revision=1, description="d")
        assert upd.ok and upd.data.prompt.revision == 2 and upd.data.prompt.template == "Explain {topic}"
        rendered = tools["agent_render_authored_prompt"](prompt_id="p1", arguments={"topic": "CAS"})
        assert rendered.data.messages[0].content == "Explain CAS"
        assert tools["agent_render_authored_prompt"](prompt_id="p1").error == "prompt_argument_missing"
        assert tools["agent_delete_prompt"](prompt_id="p1").ok
        assert tools["agent_list_prompts"]().data.count == 0
        assert tools["agent_delete_prompt"](prompt_id="p1").error == "prompt_not_found"
    finally:
        reset_envelope(token)


def test_undeclared_placeholder_is_prompt_invalid(tools) -> None:
    token = _as("alice")
    try:
        assert tools["agent_add_prompt"](prompt_id="p2", template="Hi {who}").error == "prompt_invalid"
    finally:
        reset_envelope(token)


def test_owner_isolation_and_identity_required(tools) -> None:
    token = _as("alice")
    try:
        tools["agent_add_prompt"](prompt_id="p3", template="plain")
    finally:
        reset_envelope(token)
    token = _as("bob")
    try:
        assert tools["agent_list_prompts"]().data.count == 0
    finally:
        reset_envelope(token)
    assert tools["agent_list_prompts"]().error == "prompt_identity_required"
