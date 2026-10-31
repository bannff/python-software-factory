"""Regression tests for failed canonical Graph mutation envelopes."""
from __future__ import annotations

from unittest.mock import patch

from factory.graph.mcp.core_models import EntityData, RelationshipData
from factory.mcp_utils.runtime.tool_result import fail, ok
from factory.security.runtime.adapters.graph_persistence import GraphFindingPersistence

_INVOKE = "factory.security.runtime.adapters.graph_persistence._invoke"
_ENRICH_CWE = "factory.security.runtime.adapters.taxonomy_enrichment.enrich_finding_cwe"
_ENRICH_OCSF = "factory.security.runtime.adapters.taxonomy_enrichment.enrich_ocsf"


def _entity(entity_id: str, entity_type: str) -> object:
    return ok(EntityData(id=entity_id, type=entity_type, properties={}, labels=[]))


def _relationship(relationship_id: str, source_id: str, target_id: str) -> object:
    return ok(RelationshipData(
        id=relationship_id, type="DISCOVERED", source_id=source_id,
        target_id=target_id, properties={},
    ))


class TestGraphPersistenceMutationEnvelopes:
    def test_failed_action_envelope_stops_all_follow_on_writes(self) -> None:
        with patch(_INVOKE, return_value=fail("graph unavailable")) as invoke, \
             patch(_ENRICH_OCSF) as enrich_ocsf:
            result = GraphFindingPersistence().persist_analysis(
                "a1", "scan", "/src", [{"id": "f1", "title": "XSS"}],
            )

        assert result == {"persisted": False, "error": "graph unavailable"}
        assert [call.args[0] for call in invoke.call_args_list] == ["graph_graph_add_entity"]
        enrich_ocsf.assert_not_called()

    def test_failed_finding_envelope_skips_dependents_but_continues(self) -> None:
        action_id = "action-a1"
        with patch(_INVOKE, side_effect=[
            _entity(action_id, "SecurityAction"), fail("duplicate finding"),
            _entity("f2", "Finding"), _relationship(f"discovered-{action_id}-f2", action_id, "f2"),
        ]) as invoke, patch(_ENRICH_CWE) as enrich_cwe, patch(_ENRICH_OCSF) as enrich_ocsf:
            result = GraphFindingPersistence().persist_analysis(
                "a1", "scan", "/src", [
                    {"id": "f1", "title": "bad", "cwe": "CWE-79"},
                    {"id": "f2", "title": "good", "cwe": "CWE-89"},
                ],
            )

        assert result["persisted"] is False
        assert result["findings_persisted"] == 1
        assert result["error"] == "partial graph persistence: finding f1: duplicate finding"
        assert [call.args[0] for call in invoke.call_args_list] == [
            "graph_graph_add_entity", "graph_graph_add_entity",
            "graph_graph_add_entity", "graph_graph_add_relationship",
        ]
        enrich_cwe.assert_called_once_with("f2", "CWE-89")
        assert [call.args[0] for call in enrich_ocsf.call_args_list] == [action_id, "f2"]

    def test_failed_relationship_envelope_skips_finding_taxonomy_and_count(self) -> None:
        action_id = "action-a1"
        with patch(_INVOKE, side_effect=[
            _entity(action_id, "SecurityAction"), _entity("f1", "Finding"), fail("edge rejected"),
        ]), patch(_ENRICH_CWE) as enrich_cwe, patch(_ENRICH_OCSF) as enrich_ocsf:
            result = GraphFindingPersistence().persist_analysis(
                "a1", "scan", "/src", [{"id": "f1", "title": "XSS", "cwe": "CWE-79"}],
            )

        assert result["persisted"] is False
        assert result["findings_persisted"] == 0
        assert result["error"] == "partial graph persistence: relationship f1: edge rejected"
        enrich_cwe.assert_not_called()
        assert [call.args[0] for call in enrich_ocsf.call_args_list] == [action_id]
