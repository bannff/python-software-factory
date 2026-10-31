"""Bead m2ld: rubric output_entity_type drives _collect_findings at runtime.

Verifies two paths:
1. process_workflow_rl passes count_labels through to _collect_findings.
2. rl_dispatch.run_rl_loop extracts count_labels/match_on from ctx and
   forwards them to games_process_workflow_rl.
"""
from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import patch

from factory.games.runtime.workflow_rl import process_workflow_rl
from factory.mcp_utils.interface import ToolResult


def _patch_invoker(monkeypatch, fake_invoker, gt_loader=lambda app: []):
    monkeypatch.setattr(
        "factory.games.runtime.workflow_rl._get_invoker",
        lambda: fake_invoker,
    )
    monkeypatch.setattr(
        "factory.games.runtime.workflow_rl._load_gt", gt_loader,
    )


def test_collect_findings_uses_rubric_output_entity_type(monkeypatch) -> None:
    """When count_labels=['Compliance'], _collect_findings queries that label
    instead of the default Finding/ProvenExploit pair."""
    collected_labels: list[str] = []

    def fake_invoker(tool_name: str, **kwargs):
        if tool_name == "graph_graph_find_entities":
            collected_labels.append(kwargs["entity_type"])
            return ToolResult(data=SimpleNamespace(
                entities=[SimpleNamespace(properties={"id": "c-1"})],
            ))
        if tool_name == "evals_evals_score_gt":
            return ToolResult(data={"precision": 1.0, "recall": 1.0, "f1": 1.0,
                                    "true_positives": 1, "false_positives_count": 0,
                                    "false_negatives": 0})
        if tool_name == "evals_evals_persist_score":
            return {"persisted": True, "doc_id": "eval-test"}
        raise AssertionError(f"unexpected tool: {tool_name}")

    _patch_invoker(monkeypatch, fake_invoker,
                   gt_loader=lambda app: [{"control_id": "SOC2-1"}])

    result = process_workflow_rl(
        graph_id="g-compliance",
        run_id="run-audit-1",
        vuln_class="",
        domain_class="compliance",
        count_labels=["Compliance"],
        target_app="AuditApp",
    )

    # _collect_findings queried "Compliance" (not Finding/ProvenExploit)
    assert collected_labels == ["Compliance"]
    assert result["scoring"]["f1"] == 1.0


def test_collect_findings_uses_default_when_count_labels_none(monkeypatch) -> None:
    """When count_labels is None, the security default (Finding, ProvenExploit) is used."""
    queried_tools: list[tuple[str, dict]] = []

    def fake_invoker(tool_name: str, **kwargs):
        queried_tools.append((tool_name, kwargs))
        if tool_name == "graph_graph_get_findings_for_run":
            return {"rows": [], "count": 0}
        if tool_name == "graph_graph_find_entities":
            return ToolResult(data=SimpleNamespace(entities=[]))
        if tool_name == "evals_evals_score_gt":
            return ToolResult(data={"precision": 0, "recall": 0, "f1": 0,
                                    "true_positives": 0, "false_positives_count": 0,
                                    "false_negatives": 0})
        if tool_name == "evals_evals_persist_score":
            return {"persisted": True, "doc_id": "eval-test"}
        raise AssertionError(f"unexpected tool: {tool_name}")

    _patch_invoker(monkeypatch, fake_invoker)

    process_workflow_rl(
        graph_id="g-sec",
        run_id="run-sec-1",
        vuln_class="IDOR",
        count_labels=None,
        target_app="WebGoat",
    )

    # Default: typed Finding query + ProvenExploit entity query
    tool_names = [t[0] for t in queried_tools]
    assert "graph_graph_get_findings_for_run" in tool_names
    pe_calls = [t for t in queried_tools
                if t[0] == "graph_graph_find_entities"
                and t[1].get("entity_type") == "ProvenExploit"]
    assert len(pe_calls) == 1


def test_rl_dispatch_forwards_count_labels_and_match_on_from_ctx() -> None:
    """run_rl_loop extracts count_labels/match_on from ctx and passes them
    to games_process_workflow_rl."""
    from factory.agent.runtime.rl_dispatch import run_rl_loop

    captured_kwargs: dict = {}

    def fake_invoker(tool_name: str, **kwargs):
        if tool_name == "games_process_workflow_rl":
            captured_kwargs.update(kwargs)
            return {"skipped": False}
        return {}

    with patch("factory.mcp_utils.interface.get_service", return_value=fake_invoker):
        run_rl_loop("g-compliance", {
            "run_id": "run-1",
            "vuln_class": "",
            "domain_class": "compliance",
            "target_app": "AuditApp",
            "count_labels": "Compliance",
            "match_on": ["control_id", "scope"],
        })

    assert captured_kwargs["count_labels"] == ["Compliance"]
    assert captured_kwargs["match_on"] == ["control_id", "scope"]


def test_rl_dispatch_passes_none_when_ctx_lacks_rubric_fields() -> None:
    """When ctx has no count_labels/match_on, None is passed (preserving default)."""
    from factory.agent.runtime.rl_dispatch import run_rl_loop

    captured_kwargs: dict = {}

    def fake_invoker(tool_name: str, **kwargs):
        if tool_name == "games_process_workflow_rl":
            captured_kwargs.update(kwargs)
            return {"skipped": False}
        return {}

    with patch("factory.mcp_utils.interface.get_service", return_value=fake_invoker):
        run_rl_loop("g-sec", {
            "run_id": "run-2",
            "vuln_class": "IDOR",
            "target_app": "WebGoat",
        })

    assert captured_kwargs["count_labels"] is None
    assert captured_kwargs["match_on"] is None
