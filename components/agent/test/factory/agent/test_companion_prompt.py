"""Tests for the Companion X system prompt constant."""

from __future__ import annotations

from factory.agent.runtime.companion.prompt import COMPANION_X_PROMPT


class TestCompanionPrompt:
    """Verify the system prompt is well-formed."""

    def test_prompt_is_non_empty_string(self) -> None:
        """COMPANION_X_PROMPT is a non-empty string."""
        assert isinstance(COMPANION_X_PROMPT, str)
        assert len(COMPANION_X_PROMPT) > 0

    def test_prompt_contains_identity(self) -> None:
        """Prompt tells the agent what it is."""
        assert "Companion X" in COMPANION_X_PROMPT


def test_prompt_serializes_tool_calls() -> None:
    """bd:python-factory-ads4 — prompt instructs serial tool calls.

    Companion-X chat fired duplicate parallel tool calls because the prompt
    encouraged chaining. Step 1 of the fix replaces that guidance with an
    explicit "one tool at a time" rule.
    """
    assert "Call one tool at a time" in COMPANION_X_PROMPT, (
        "Prompt must explicitly tell the agent to issue one tool call per turn."
    )
    assert "chain multiple tool calls" not in COMPANION_X_PROMPT, (
        "Old chain-multiple language must be gone — it triggered the parallel "
        "tool_use bug."
    )


def test_prompt_does_not_name_dead_tools() -> None:
    """bd:python-factory-ads4 — prompt no longer references unregistered tools.

    ``agent_invoke_swarm`` and ``agent_invoke_graph`` are MCP prompts, NOT
    registered tools. Naming them as call targets caused the agent to emit
    invalid tool calls (which Strands then retried — multiplying the load).
    Only ``agent_launch_swarm`` is a real tool today.
    """
    assert "agent_invoke_swarm" not in COMPANION_X_PROMPT, (
        "agent_invoke_swarm is a prompt, not a tool — must not appear as a "
        "callable in the system prompt."
    )
    assert "agent_invoke_graph" not in COMPANION_X_PROMPT, (
        "agent_invoke_graph is a prompt, not a tool — must not appear as a "
        "callable in the system prompt."
    )


def test_prompt_names_real_tools() -> None:
    """bd:python-factory-czpw.1 — prompt teaches the REAL create+spawn
    capabilities and stops bluffing about the chat-EXCLUDED launcher.

    The chat agent now CREATES personas (``agent_create_agent``) and
    SPAWNS them as sub-agents (``spawn_subagent``). It must NOT reference
    ``agent_launch_swarm`` — that tool is excluded from the chat surface
    (``EXCLUDED_TOOLS``), so naming it as a call target made the agent
    hallucinate a tool it cannot see (the original czpw.1 bug).
    """
    assert "agent_create_agent" in COMPANION_X_PROMPT, (
        "Prompt must teach the create-on-the-fly capability."
    )
    assert "spawn_subagent" in COMPANION_X_PROMPT, (
        "Prompt must teach the spawn-sub-agent capability."
    )
    # bd:python-factory-2vvq8 — the always-on spawn-routing negative was
    # hoisted from the companion-x-behavior skill into the prompt. The launcher
    # may now be NAMED, but only as an explicitly off-limits tool — never as a
    # call target. Guard the callable form stays absent and the prohibition is
    # present (the original czpw.1 bug was naming it AS a usable tool).
    assert "agent_launch_swarm(" not in COMPANION_X_PROMPT, (
        "agent_launch_swarm must never appear as a callable form — it is "
        "excluded from the chat surface (czpw.1 bug)."
    )
    assert "agent_launch_swarm` is not on your tool list" in COMPANION_X_PROMPT, (
        "The prompt must explicitly mark agent_launch_swarm as off-limits "
        "(hoisted always-on rule, bd:python-factory-2vvq8)."
    )


def test_prompt_teaches_spawn_swarm() -> None:
    """bd:python-factory-t8o1g — prompt teaches the native ``spawn_swarm``
    multi-agent composition tool alongside the single ``spawn_subagent``.

    The chat agent can now assemble several registered personas into a
    collaborating Strands swarm on one task. The prompt must name the real
    tool (``spawn_swarm(agent_ids, task)``) so the LLM knows when to reach
    for a team vs a single specialist.
    """
    assert "spawn_swarm" in COMPANION_X_PROMPT, (
        "Prompt must teach the spawn-swarm (multi-agent team) capability."
    )
    # The swarm tool takes a LIST of ids — the teaching must distinguish it
    # from the single-agent spawn so the LLM picks the right one.
    assert "agent_ids" in COMPANION_X_PROMPT, (
        "Prompt must reference the spawn_swarm agent_ids list arg so the "
        "agent knows to pass multiple personas."
    )
