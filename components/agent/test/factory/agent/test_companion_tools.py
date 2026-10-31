"""Tests for companion tool selection logic.

Verifies that select_tools() correctly filters MCP tool names based on
allowed prefixes, extra tools, and excluded tools.
"""

from __future__ import annotations

import pytest
from hypothesis import given, strategies as st, settings

from factory.agent.runtime.companion.tools import (
    ALLOWED_BRICK_PREFIXES,
    EXCLUDED_TOOLS,
    EXTRA_TOOLS,
    select_tools,
)


class TestSelectTools:
    """Unit tests for select_tools()."""

    def test_happy_path_filters_by_prefix(self) -> None:
        """Allowed-prefix tools are included."""
        tools = ["security_scan", "graph_find_entities", "kb_search", "unknown_tool"]
        result = select_tools(tools)
        assert "security_scan" in result
        assert "graph_find_entities" in result
        assert "kb_search" in result
        assert "unknown_tool" not in result

    def test_empty_input_returns_empty(self) -> None:
        """Empty tool list produces empty result."""
        assert select_tools([]) == []

    def test_no_matches_returns_empty(self) -> None:
        """Tools with no matching prefix produce empty result."""
        tools = ["foo_bar", "baz_qux", "nope_thing"]
        assert select_tools(tools) == []

    def test_excluded_tools_removed(self) -> None:
        """Excluded tools are filtered out, but workflow-launch tools are kept.

        See bd python-factory-pizn — strands-expert confirmed the chat agent
        MUST be able to launch curated registry workflows (agent_invoke_swarm,
        agent_invoke_graph). Only ad-hoc launch (agent_launch_swarm — BOTH
        prefix forms, bd:python-factory-esb6n) and the four internal contract
        tools are excluded.
        """
        tools = [
            "agent_reason",
            "agent_get_views",
            "agent_health_check",
            "agent_get_capabilities",
            "agent_launch_swarm",        # flat-view single-prefix (chat surface)
            "agent_agent_launch_swarm",  # aggregator double-prefix
            "agent_invoke_swarm",
            "agent_invoke_graph",
            "security_scan",
        ]
        result = select_tools(tools)
        for excluded in (
            "agent_reason", "agent_get_views",
            "agent_health_check", "agent_get_capabilities",
            "agent_launch_swarm", "agent_agent_launch_swarm",
        ):
            assert excluded not in result, f"{excluded} should be excluded"
        assert "agent_invoke_swarm" in result
        assert "agent_invoke_graph" in result
        assert "security_scan" in result

    def test_extra_tools_included(self) -> None:
        """Extra tools are included when present in input.

        bd:python-factory-3hkqx — single-prefix names match what the FLAT
        view publishes (the chat agent's transport).
        """
        tools = ["ui_render_brick_view", "random_thing"]
        result = select_tools(tools)
        assert "ui_render_brick_view" in result
        assert "random_thing" not in result

    def test_extra_tools_not_invented(self) -> None:
        """Extra tools are NOT added if absent from input list."""
        result = select_tools(["security_scan"])
        assert "ui_render_brick_view" not in result

    def test_result_is_sorted(self) -> None:
        """Output is sorted alphabetically."""
        tools = ["kb_search", "auth_check", "graph_find_entities"]
        result = select_tools(tools)
        assert result == sorted(result)

    def test_duplicates_in_input_produce_unique_output(self) -> None:
        """Duplicate tool names in input don't produce duplicates."""
        tools = ["security_scan", "security_scan", "security_scan"]
        result = select_tools(tools)
        assert result == ["security_scan"]

    def test_all_allowed_prefixes_match(self) -> None:
        """Every allowed prefix actually selects matching tools."""
        tools = [f"{prefix}_test_tool" for prefix in ALLOWED_BRICK_PREFIXES]
        result = select_tools(tools)
        assert len(result) == len(ALLOWED_BRICK_PREFIXES)

    def test_excluded_tool_in_extra_tools_still_excluded(self) -> None:
        """If a tool is both in EXTRA_TOOLS and EXCLUDED_TOOLS, exclusion wins."""
        # Simulate by checking the logic: excluded set is subtracted last
        tools = list(EXCLUDED_TOOLS)
        result = select_tools(tools)
        for excluded in EXCLUDED_TOOLS:
            assert excluded not in result

    def test_prefix_must_be_followed_by_underscore(self) -> None:
        """Prefix match requires underscore separator (e.g. 'security_' not 'securityfoo')."""
        tools = ["securityfoo", "security_foo"]
        result = select_tools(tools)
        assert "securityfoo" not in result
        assert "security_foo" in result

    def test_bare_prefix_not_matched(self) -> None:
        """A tool named exactly like a prefix (no underscore suffix) is not matched."""
        tools = ["security", "graph", "kb"]
        assert select_tools(tools) == []


class TestSelectToolsProperties:
    """Property-based tests for select_tools()."""

    @given(
        tool_names=st.lists(
            st.text(min_size=1, max_size=40, alphabet=st.characters(
                whitelist_categories=("L", "N"), whitelist_characters="_-"
            )),
            max_size=100,
        )
    )
    @settings(max_examples=50)
    def test_output_is_subset_of_input(self, tool_names: list[str]) -> None:
        """Every selected tool must come from the input list."""
        result = select_tools(tool_names)
        for name in result:
            assert name in tool_names

    @given(
        tool_names=st.lists(
            st.text(min_size=1, max_size=40, alphabet=st.characters(
                whitelist_categories=("L", "N"), whitelist_characters="_-"
            )),
            max_size=100,
        )
    )
    @settings(max_examples=50)
    def test_no_excluded_tools_in_output(self, tool_names: list[str]) -> None:
        """Excluded tools never appear in output."""
        result = select_tools(tool_names)
        for name in result:
            assert name not in EXCLUDED_TOOLS

    @given(
        tool_names=st.lists(
            st.text(min_size=1, max_size=40, alphabet=st.characters(
                whitelist_categories=("L", "N"), whitelist_characters="_-"
            )),
            max_size=100,
        )
    )
    @settings(max_examples=50)
    def test_output_is_always_sorted(self, tool_names: list[str]) -> None:
        """Output is always sorted regardless of input order."""
        result = select_tools(tool_names)
        assert result == sorted(result)

    @given(
        tool_names=st.lists(
            st.text(min_size=1, max_size=40, alphabet=st.characters(
                whitelist_categories=("L", "N"), whitelist_characters="_-"
            )),
            max_size=100,
        )
    )
    @settings(max_examples=50)
    def test_output_has_no_duplicates(self, tool_names: list[str]) -> None:
        """Output never contains duplicates."""
        result = select_tools(tool_names)
        assert len(result) == len(set(result))

    @given(
        tool_names=st.lists(
            st.text(min_size=1, max_size=40, alphabet=st.characters(
                whitelist_categories=("L", "N"), whitelist_characters="_-"
            )),
            max_size=100,
        )
    )
    @settings(max_examples=50)
    def test_idempotent(self, tool_names: list[str]) -> None:
        """Running select_tools twice on the same input gives the same result."""
        first = select_tools(tool_names)
        second = select_tools(tool_names)
        assert first == second
