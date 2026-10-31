"""Phase 4 share of the cross-phase E2E substrate test (epic
python-factory-hadbi). Sibling of agent-brick
``test_domain_agnostic_substrate_e2e.py``; sits in games-brick test
tree because it imports ``factory.games.runtime`` directly (no
cross-brick imports per polylith tenet). Verdicts cited:
meta-architect ``9a4aba3c`` and strands-expert ``9b6d46cd``.
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

from factory.games.runtime._rl_stages import (
    DEFAULT_COUNT_LABELS, _collect_findings,
)
from factory.games.runtime.game_pipeline import process_game_finished


class TestPhase4CollectFindingsDomainAgnostic:
    """``count_labels=("DomainItem",)`` queries find_entities exactly
    once; no Finding/ProvenExploit calls; default pair preserved."""

    def test_collect_findings_uses_domain_label(self):
        calls: list[tuple[str, dict]] = []

        def invoker(name, **kw):
            calls.append((name, kw))
            return {"rows": [], "entities": [], "count": 0}

        _collect_findings(
            invoker, run_id="qa-run-4",
            count_labels=("DomainItem",),
        )
        names = [c[0] for c in calls]
        assert names == ["graph_graph_find_entities"]
        assert calls[0][1]["entity_type"] == "DomainItem"
        assert "graph_graph_get_findings_for_run" not in names

    def test_collect_findings_default_security_pair_unchanged(self):
        assert DEFAULT_COUNT_LABELS == ("Finding", "ProvenExploit")
        calls: list[tuple[str, dict]] = []

        def invoker(name, **kw):
            calls.append((name, kw))
            return {"rows": [], "entities": [], "count": 0}

        _collect_findings(invoker, run_id="qa-run")
        names = [c[0] for c in calls]
        assert "graph_graph_get_findings_for_run" in names
        types = [
            c[1]["entity_type"] for c in calls
            if c[0] == "graph_graph_find_entities"
        ]
        assert types == ["ProvenExploit"]


class TestPhase4DomainClassMemoryRecall:
    """``domain_class=qa_domain`` emits dual tags: scan-learnings
    (back-compat) AND qa_domain-learnings (domain-suffixed)."""

    def test_emit_learning_dual_tags_qa_domain(self):
        invoker = MagicMock(return_value={"ok": True})
        with patch(
            "factory.games.runtime.game_pipeline._get_invoker",
            return_value=invoker,
        ):
            process_game_finished({
                "game_id": "qa-001", "game_type": "scan",
                "winner": 1, "reward": {1: 1.0}, "move_count": 1,
                "move_history": [
                    {"action": "submit_finding",
                     "move": {"match": "vulnerability"}},
                ],
                "config": {"domain_class": "qa_domain", "run_id": "r-qa"},
                "players": {1: "agent-qa"},
            })

        for call in reversed(invoker.call_args_list):
            if call[0] and call[0][0] == "memory_memory_store":
                kwargs = call[1]
                break
        else:
            raise AssertionError("memory_memory_store never invoked")

        # Order pinned: [domain, scan-learnings, {domain}-learnings, run_id].
        # bd:python-factory-vs1vu — tags ride inside metadata so they land
        # in MemoryQuery.metadata.tags (the lin6p filter read shape).
        assert kwargs["metadata"]["tags"] == [
            "qa_domain", "scan-learnings", "qa_domain-learnings", "r-qa",
        ]

    def test_vuln_class_fallback_when_no_domain_class(self):
        """Substrate-prep promise: security flows byte-identical when
        only legacy ``vuln_class`` config key is set."""
        invoker = MagicMock(return_value={"ok": True})
        with patch(
            "factory.games.runtime.game_pipeline._get_invoker",
            return_value=invoker,
        ):
            process_game_finished({
                "game_id": "sec-001", "game_type": "scan",
                "winner": 1, "reward": {1: 1.0}, "move_count": 1,
                "move_history": [],
                "config": {"vuln_class": "security_idor", "run_id": "r-sec"},
                "players": {1: "sec-agent"},
            })

        for call in reversed(invoker.call_args_list):
            if call[0] and call[0][0] == "memory_memory_store":
                kwargs = call[1]
                break
        else:
            raise AssertionError("memory_memory_store never invoked")

        # vuln_class wins as fallback — back-compat shape preserved.
        # bd:python-factory-vs1vu — metadata.tags is the canonical surface.
        assert kwargs["metadata"]["tags"] == [
            "security_idor", "scan-learnings",
            "security_idor-learnings", "r-sec",
        ]
