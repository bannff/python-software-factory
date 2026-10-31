"""Catalog, strict-contract, and active-prompt parity for spawn tools."""
from __future__ import annotations

from pydantic import BaseModel
import pytest


def test_spawn_catalog_has_exact_typed_public_names() -> None:
    from factory.agent.server import create_tool_catalog
    from factory.mcp_server.runtime.public_admission import project_public_tools

    catalog = create_tool_catalog()
    projection = project_public_tools((("agent", catalog.tool_map()),))
    public = {item.public_name for item in projection.admitted}
    expected = {
        "agent_spawn_subagent", "agent_spawn_swarm", "agent_spawn_graph",
    }
    assert expected <= public
    for local_name in ("spawn_subagent", "spawn_swarm", "spawn_graph"):
        handler = catalog.tool_map()[local_name].fn
        assert issubclass(handler._mcp_input_model, BaseModel)
        assert issubclass(handler._mcp_output_model, BaseModel)


def test_active_prompts_and_developer_persona_use_canonical_public_names() -> None:
    from factory.agent.registry.defaults_developer import DEVELOPER_AGENT
    from factory.agent.runtime.companion.prompt import COMPANION_X_PROMPT

    canonical = {
        "agent_spawn_subagent", "agent_spawn_swarm", "agent_spawn_graph",
    }
    assert all(name in COMPANION_X_PROMPT for name in canonical)
    assert all(name in DEVELOPER_AGENT.description for name in canonical)
    for deleted in ("`spawn_subagent", "`spawn_swarm", "`spawn_graph"):
        assert deleted not in COMPANION_X_PROMPT


@pytest.mark.asyncio
async def test_invalid_spawn_call_returns_typed_successful_domain_envelope() -> None:
    from factory.agent.server import create_tool_catalog

    result = await create_tool_catalog().call_tool(
        "spawn_graph",
        {"agent_ids": ["missing"], "edges": [], "task": "inspect"},
    )
    assert result.is_error is False
    assert result.structured_content["ok"] is True
    assert result.structured_content["data"]["status"] == "rejected"
    assert result.structured_content["data"]["error_code"] == "scope_unavailable"


def test_developer_persona_has_exact_devtools_scope() -> None:
    from factory.agent.registry.defaults_developer import DEVELOPER_AGENT

    assert DEVELOPER_AGENT.exact_tools is True
    assert DEVELOPER_AGENT.tools == [
        "devtools_read_file", "devtools_list_dir", "devtools_search",
        "devtools_git_status", "devtools_git_diff", "devtools_git_log",
        "devtools_write_file", "devtools_edit_file", "devtools_run_command",
        "devtools_cancel_command", "devtools_git_stage", "devtools_git_commit", "devtools_git_push",
    ]


def test_generic_selector_personas_inherit_the_process_default_model() -> None:
    """Regression (live 2026-09-30): personas whose ``model`` was the bare
    ``openrouter`` selector hard-required OPENROUTER_MODEL, so every
    spawn failed on deployments whose default provider is anything else
    (e.g. the Casper openai-compat profile) — chat worked, spawns did
    not. Personas meant to run on the deployment's default chat provider
    must leave ``model`` empty so ``LangChainModelCache.effective_id``
    inherits COMPANION_X_CHAT_MODEL. Personas pinned to a genuinely
    special backend (e.g. ``ollama/foundation-sec``) keep their override
    and are excluded here."""
    from factory.agent.registry.unified import unified_personas

    generic_backend_prefixes = ("openrouter", "openai-compat")
    for config in unified_personas():
        if config.model.startswith(generic_backend_prefixes):
            raise AssertionError(
                f"persona {config.id!r} pins generic selector "
                f"model={config.model!r}; it must be empty to inherit "
                "COMPANION_X_CHAT_MODEL"
            )
