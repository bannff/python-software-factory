"""bd python-factory-tmlrx + python-factory-twxj0 — RL lifecycle event coverage.

Companion file to ``test_workflow_rl_domain_class.py``. Covers:

* RL events emit both ``domain_class`` AND ``vuln_class``.
* ``_plan_learning`` falls back to ``vuln_class`` when ``domain_class``
  is empty.
* Hypothesis property — arbitrary domain_class strings flow through.
"""

from __future__ import annotations

from unittest.mock import patch

from hypothesis import given, settings, strategies as st

from factory.games.runtime.workflow_rl import process_workflow_rl


def _patch_invoker(monkeypatch, fake_invoker, gt_loader=lambda app: []):
    monkeypatch.setattr(
        "factory.games.runtime.workflow_rl._get_invoker",
        lambda: fake_invoker,
    )
    monkeypatch.setattr(
        "factory.games.runtime.workflow_rl._load_gt", gt_loader,
    )


@patch("factory.games.runtime.workflow_rl.event_emitter.emit")
@patch("factory.games.runtime.workflow_rl._plan_learning")
@patch("factory.games.runtime.workflow_rl._plan_reward")
@patch("factory.games.runtime.workflow_rl._score")
@patch("factory.games.runtime.workflow_rl._load_gt")
@patch("factory.games.runtime.workflow_rl._collect_findings")
@patch("factory.games.runtime.workflow_rl._get_invoker")
def test_rl_events_carry_both_vuln_and_domain_class(
    mock_get_invoker, mock_collect_findings, mock_load_gt, mock_score,
    mock_plan_reward, mock_plan_learning, mock_emit,
):
    """Each emitted RL event payload carries both vuln_class and domain_class."""
    mock_get_invoker.return_value = lambda *a, **kw: {}
    mock_collect_findings.return_value = []
    mock_load_gt.return_value = []
    mock_score.return_value = {
        "precision": 0.5, "recall": 1.0, "f1": 0.67,
        "true_positives": 1, "false_positives_count": 0, "false_negatives": 0,
    }
    mock_plan_reward.return_value = {
        "eligible": True, "amount": 67.0, "status": "pending_event",
    }
    mock_plan_learning.return_value = {
        "stored": False, "status": "pending_event",
    }

    process_workflow_rl(
        graph_id="dast-wine", run_id="run-1",
        vuln_class="TASTING", domain_class="wine",
        workflow_type="dast", target_app="WineApp",
    )

    for call in mock_emit.call_args_list:
        payload = call.args[1]
        assert payload["domain_class"] == "wine", call
        assert payload["vuln_class"] == "TASTING", call


def test_domain_class_falls_back_to_vuln_class_for_memory_tag(monkeypatch) -> None:
    """When domain_class is empty, _plan_learning falls back to vuln_class."""
    from factory.games.runtime._rl_planning import _plan_learning

    plan = _plan_learning(
        scoring={"f1": 0.0, "precision": 0.0, "recall": 0.0},
        run_id="run-4",
        vuln_class="IDOR", wtype="dast", target_app="WebGoat",
        domain_class="",
    )
    assert plan["domain"] == "IDOR"
    assert "IDOR" in plan["content"]


@settings(max_examples=15, deadline=None)
@given(domain=st.text(
    min_size=1, max_size=24,
    alphabet=st.characters(whitelist_categories=("L", "N")),
))
def test_arbitrary_domain_class_strings_flow_through(domain: str) -> None:
    """Hypothesis: any domain_class string lands in the memory plan content."""
    from factory.games.runtime._rl_planning import _plan_learning

    plan = _plan_learning(
        scoring={"f1": 0.5, "precision": 0.5, "recall": 0.5},
        run_id="run-h", vuln_class="", wtype="dast", target_app="App",
        domain_class=domain,
    )
    assert plan["domain"] == domain
    assert domain in plan["content"]
