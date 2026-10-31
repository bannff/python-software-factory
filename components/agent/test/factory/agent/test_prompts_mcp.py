"""Regression coverage for Agent-owned native MCP prompts."""

from __future__ import annotations

import asyncio

from factory.agent.server import create_tool_catalog


def test_agent_runtime_setup_prompt_matches_active_framework() -> None:
    catalog = create_tool_catalog()
    prompts = asyncio.run(catalog.list_prompts())
    names = {prompt.name for prompt in prompts}

    assert "agent_langchain_setup" in names
    assert "agent_strands_setup" not in names

    rendered = asyncio.run(catalog.render_prompt("agent_langchain_setup"))
    text = rendered.messages[0].content.text
    assert "LangChain and LangGraph" in text
    assert "MCP v2" in text
    assert "do not introduce another runtime" in text
    assert "strands-agents" not in text
