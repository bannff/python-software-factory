"""Tests for security presets registered by _get_default_agent().

Verifies that the default agent ships with the expected built-in
swarm and agent configurations from registry/defaults.py.
"""

from __future__ import annotations

from factory.agent.server import _get_default_agent
from factory.agent.registry.defaults import (
    get_default_swarms, get_default_agents, get_default_graphs,
)


class TestSecurityPresets:
    """Verify _get_default_agent() registers the correct presets."""

    def test_swarm_registry_has_expected_entries(self):
        """Default agent registers all built-in swarm presets."""
        agent = _get_default_agent()
        assert len(agent.swarm_registry.swarms) == len(get_default_swarms())

    def test_swarm_ids_match_defaults(self):
        """Swarm IDs match those defined in get_default_swarms()."""
        agent = _get_default_agent()
        expected_ids = {s.id for s in get_default_swarms()}
        actual_ids = set(agent.swarm_registry.swarms.keys())
        assert actual_ids == expected_ids

    def test_swarm_security_recon_present(self):
        """security-recon swarm is registered with correct structure."""
        agent = _get_default_agent()
        swarm = agent.swarm_registry.swarms.get("security-recon")
        assert swarm is not None
        assert swarm.name == "Security Recon Swarm"
        assert swarm.entry_point == "recon-agent"
        assert len(swarm.agents) == 3

    def test_swarm_code_review_present(self):
        """code-review swarm is registered with correct structure."""
        agent = _get_default_agent()
        swarm = agent.swarm_registry.swarms.get("code-review")
        assert swarm is not None
        assert swarm.name == "Code Review Swarm"
        assert swarm.entry_point == "static-analyzer"
        assert len(swarm.agents) == 2

    def test_idor_experiment_loop_graph_removed(self):
        """idor-experiment-loop graph was removed in the Strands modernization
        epic (bd python-factory-h2db) — it wrapped the deprecated idor-detection
        swarm. Use the rt-scan-idor graph instead."""
        agent = _get_default_agent()
        graph = agent.graph_registry.graphs.get("idor-experiment-loop")
        assert graph is None

    def test_agent_registry_has_three_entries(self):
        """Default agent registry has all built-in agent entries."""
        agent = _get_default_agent()
        assert len(agent.agent_registry.agents) == len(get_default_agents())

    def test_agent_ids_match_defaults(self):
        """Agent IDs match those defined in get_default_agents()."""
        agent = _get_default_agent()
        expected_ids = {a.id for a in get_default_agents()}
        actual_ids = set(agent.agent_registry.agents.keys())
        assert actual_ids == expected_ids

    def test_security_analyst_present(self):
        """security-analyst agent is registered."""
        agent = _get_default_agent()
        ag = agent.agent_registry.agents.get("security-analyst")
        assert ag is not None
        assert ag.name == "Security Analyst"

    def test_eval_runner_present(self):
        """eval-runner agent is registered."""
        agent = _get_default_agent()
        ag = agent.agent_registry.agents.get("eval-runner")
        assert ag is not None
        assert ag.name == "Evaluation Runner"

    def test_compliance_checker_present(self):
        """compliance-checker agent is registered."""
        agent = _get_default_agent()
        ag = agent.agent_registry.agents.get("compliance-checker")
        assert ag is not None
        assert ag.name == "Compliance Checker"

    def test_registries_are_independent_instances(self):
        """Each call to _get_default_agent() returns fresh registries."""
        a1 = _get_default_agent()
        a2 = _get_default_agent()
        assert a1.swarm_registry is not a2.swarm_registry
        assert a1.agent_registry is not a2.agent_registry

    def test_configured_agent_root_is_reused(self, tmp_path, monkeypatch):
        """Companion composition can retain owner-scoped config across rebuilds."""
        root = tmp_path / "agent-config"
        monkeypatch.setenv("FACTORY_AGENT_CONFIG_DIR", str(root))
        first = _get_default_agent()
        second = _get_default_agent()
        assert first.config_dir == root.resolve()
        assert second.config_dir == root.resolve()
        assert root.is_dir()

    def test_graph_registry_has_expected_entries(self):
        """Graph registry contains all built-in graph presets."""
        agent = _get_default_agent()
        expected = get_default_graphs()
        assert len(agent.graph_registry.graphs) == len(expected)
        assert set(agent.graph_registry.graphs.keys()) == {g.id for g in expected}

    def test_tool_registry_empty(self):
        """Tool registry starts empty (no defaults)."""
        agent = _get_default_agent()
        assert len(agent.tool_registry.tools) == 0

    def test_agent_is_initialized(self):
        """Default agent is marked as initialized."""
        agent = _get_default_agent()
        assert agent._initialized is True
