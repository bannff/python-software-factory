"""bd python-factory-tmlrx + python-factory-twxj0 — domain_class threading.

The RL pipeline reads ``domain_class`` (with ``vuln_class`` fallback),
forwards it into ``_collect_findings`` (via ``count_labels``/
``taxonomy_edges``), ``_plan_learning`` (memory tag prefix),
``_build_report`` (dual-emit report dict), and the persist invocation.

Hypothesis property + lifecycle event coverage live in
``test_workflow_rl_domain_class_lifecycle.py`` to keep both files <200 LOC.
"""

from __future__ import annotations

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


def test_domain_class_dual_emitted_in_report(monkeypatch) -> None:
    """Report dict carries both vuln_class AND domain_class."""
    def fake_invoker(tool_name, **kwargs):
        if tool_name == "graph_graph_get_findings_for_run":
            return {"rows": []}
        if tool_name == "graph_graph_find_entities":
            return {"entities": []}
        if tool_name == "evals_evals_score_gt":
            return ToolResult(data={"f1": 0.7, "precision": 0.7, "recall": 0.7,
                                    "true_positives": 1, "false_positives_count": 0,
                                    "false_negatives": 0})
        if tool_name == "evals_evals_persist_score":
            return {"persisted": True}
        raise AssertionError(f"unexpected tool: {tool_name}")

    _patch_invoker(monkeypatch, fake_invoker,
                   lambda app: [{"cwe": "x", "file": "y"}])

    report = process_workflow_rl(
        graph_id="dast-wine", run_id="run-WineApp-1",
        vuln_class="TASTING", domain_class="wine",
        workflow_type="dast", target_app="WineApp",
    )
    assert report["domain_class"] == "wine"
    assert report["vuln_class"] == "TASTING"


def test_persist_receives_domain_class(monkeypatch) -> None:
    """evals_evals_persist_score gets domain_class kwarg from the pipeline."""
    persist_kwargs: dict = {}

    def fake_invoker(tool_name, **kwargs):
        if tool_name == "graph_graph_get_findings_for_run":
            return {"rows": []}
        if tool_name == "graph_graph_find_entities":
            return {"entities": []}
        if tool_name == "evals_evals_score_gt":
            return ToolResult(data={"f1": 0.5, "precision": 0.5, "recall": 0.5})
        if tool_name == "evals_evals_persist_score":
            persist_kwargs.update(kwargs)
            return {"persisted": True}
        raise AssertionError(f"unexpected tool: {tool_name}")

    _patch_invoker(monkeypatch, fake_invoker,
                   lambda app: [{"cwe": "x", "file": "y"}])

    process_workflow_rl(
        graph_id="dast-wine", run_id="run-WineApp-2",
        vuln_class="", domain_class="wine",
        workflow_type="dast", target_app="WineApp",
    )

    assert persist_kwargs.get("domain_class") == "wine"
    assert persist_kwargs.get("vuln_class") == ""


def test_count_labels_and_taxonomy_edges_thread_through(monkeypatch) -> None:
    """count_labels + taxonomy_edges reach the typed Finding query verbatim."""
    seen: dict = {}

    def fake_invoker(tool_name, **kwargs):
        if tool_name == "graph_graph_get_findings_for_run":
            seen.update(kwargs)
            return {"rows": []}
        if tool_name == "graph_graph_find_entities":
            return {"entities": []}
        if tool_name == "evals_evals_score_gt":
            return ToolResult(data={"f1": 0.0})
        if tool_name == "evals_evals_persist_score":
            return {"persisted": True}
        raise AssertionError(f"unexpected tool: {tool_name}")

    _patch_invoker(monkeypatch, fake_invoker, lambda app: [])

    custom_edges = [
        {"relationship_type": "BELONGS_TO_CATEGORY",
         "target_label": "WineCategory",
         "target_props": {"name": "category_name"}},
    ]

    process_workflow_rl(
        graph_id="dast-wine", run_id="run-3",
        domain_class="wine",
        # "Finding" must remain in count_labels for taxonomy_edges to take effect —
        # only the typed Finding query reads taxonomy edges.
        count_labels=["Finding", "WineFinding"],
        taxonomy_edges=custom_edges,
        workflow_type="dast", target_app="WineApp",
    )
    assert seen.get("taxonomy_edges") == custom_edges
