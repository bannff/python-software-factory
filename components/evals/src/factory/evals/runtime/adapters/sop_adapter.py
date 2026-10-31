"""Eval SOP adapter — 4-phase workflow: Plan→Data→Eval→Report.

Sessions persisted to .object_store/sop_sessions.json via sop_store.py.
Completion artifacts flow through the runtime-composed persistence port.
"""
from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass, field
from typing import Any

from ..ports import EvalPersistencePort
from . import sop_store
from .persistence import NoOpEvalPersistence

logger = logging.getLogger(__name__)


@dataclass
class SOPState:
    id: str = ""
    phase: str = "plan"
    agent_description: str = ""
    agent_tools: list[str] = field(default_factory=list)
    evaluation_goals: str = ""
    eval_plan: dict[str, Any] = field(default_factory=dict)
    test_cases: list[dict[str, Any]] = field(default_factory=list)
    eval_results: dict[str, Any] = field(default_factory=dict)
    report: str = ""


def create_sop_session(
    agent_description: str,
    agent_tools: list[str] | None = None,
    evaluation_goals: str = "",
) -> dict[str, Any]:
    session_id = str(uuid.uuid4())[:8]
    tools = agent_tools or []
    plan = {
        "agent_description": agent_description,
        "agent_tools": tools,
        "evaluation_goals": evaluation_goals,
        "recommended_evaluators": _recommend_evaluators(tools, evaluation_goals),
        "test_categories": _infer_categories(agent_description, tools),
        "success_criteria": {"min_pass_rate": 0.75, "min_avg_score": 0.7},
    }
    state = SOPState(
        id=session_id, phase="data",
        agent_description=agent_description, agent_tools=tools,
        evaluation_goals=evaluation_goals, eval_plan=plan,
    )
    sop_store.save_session(state)
    return {"session_id": session_id, "phase": "plan", "next_phase": "data", "plan": plan}


def generate_sop_test_data(
    session_id: str, num_cases: int = 10, evaluator_name: str = "output",
) -> dict[str, Any]:
    state = _get_session(session_id)
    if state.phase != "data":
        return {"error": f"Expected phase 'data', got '{state.phase}'"}
    cases = _fallback_cases(state, num_cases)
    for case in cases:
        case["metadata"]["evaluator"] = evaluator_name
    state.test_cases = cases
    state.phase = "eval"
    sop_store.save_session(state)
    return {"session_id": session_id, "phase": "data", "next_phase": "eval",
            "cases": cases, "case_count": len(cases)}


def run_sop_evaluation(
    session_id: str,
    model_id: str = "",
    system_prompt: str = "",
    evaluator_names: list[str] | None = None,
    rubric: str = "",
) -> dict[str, Any]:
    del model_id, system_prompt
    state = _get_session(session_id)
    if state.phase != "eval":
        return {"error": f"Expected phase 'eval', got '{state.phase}'"}
    from .evaluator_adapter import evaluate_output_multi

    names = evaluator_names or ["output"]
    rows = []
    for case in state.test_cases:
        value = evaluate_output_multi(
            str(case.get("input", "")), str(case.get("input", "")),
            names, rubric, case.get("expected_output"),
        )
        rows.extend(value["results"])
    total = len(rows)
    state.eval_results = {
        "case_results": rows,
        "summary": {
            "total_cases": len(state.test_cases),
            "avg_score": sum(row["score"] for row in rows) / total if total else 0.0,
            "pass_rate": sum(row["test_pass"] for row in rows) / total if total else 0.0,
        },
        "evaluators": names,
    }
    state.phase = "report"
    sop_store.save_session(state)
    return {"session_id": session_id, "phase": "eval", "next_phase": "report",
            "results": state.eval_results}


def generate_sop_report(
    session_id: str, persistence: EvalPersistencePort | None = None,
) -> dict[str, Any]:
    state = _get_session(session_id)
    if state.phase != "report":
        return {"error": f"Expected phase 'report', got '{state.phase}'"}
    from .sop_report import build_report
    state.report = build_report(state)
    state.phase = "complete"
    sop_store.save_session(state)
    adapter = persistence if persistence is not None else NoOpEvalPersistence()
    _materialize_eval_run(state, adapter)
    return {"session_id": session_id, "phase": "report", "status": "complete",
            "report": state.report}


def get_sop_session(session_id: str) -> dict[str, Any]:
    state = _get_session(session_id)
    return {"session_id": state.id, "phase": state.phase,
            "has_plan": bool(state.eval_plan), "case_count": len(state.test_cases),
            "has_results": bool(state.eval_results), "has_report": bool(state.report)}


def list_sop_sessions() -> list[dict[str, Any]]:
    return [
        {"id": s.id, "session_id": s.id, "phase": s.phase,
         "description": s.agent_description[:80], "agent": s.agent_description[:80]}
        for s in sop_store.load_all().values()
    ]


def _get_session(session_id: str) -> SOPState:
    state = sop_store.load_session(session_id)
    if state is None:
        raise ValueError(f"SOP session not found: {session_id}")
    return state


def _materialize_eval_run(
    state: SOPState, persistence: EvalPersistencePort,
) -> None:
    """Persist the completed SOP suite and run through the injected port."""
    from ..ports import EvalMetrics, EvalRun, EvalSuite
    from datetime import datetime, timezone
    now = datetime.now(timezone.utc)
    summary = state.eval_results.get("summary", {})
    persistence.persist_suite(EvalSuite(
        id=f"sop-suite-{state.id}",
        name=f"SOP: {state.agent_description[:40]}",
        description=state.evaluation_goals, cases=[],
    ))
    persistence.persist_run(
        EvalRun(id=f"sop-{state.id}", suite_id=f"sop-suite-{state.id}",
                status="completed", started_at=now, completed_at=now,
                summary=summary),
        EvalMetrics(pass_rate=summary.get("pass_rate", 0.0),
                    avg_score=summary.get("avg_score", 0.0),
                    total_cases=len(state.test_cases),
                    failed=summary.get("failed", 0)),
    )


def _recommend_evaluators(tools: list[str], goals: str) -> list[str]:
    gl = goals.lower()
    rec = (["tool_selection", "tool_parameter"] if tools else [])
    if "multi-turn" in gl: rec += ["helpfulness", "goal_success"]
    if "safety" in gl: rec.append("harmfulness")
    if "accuracy" in gl: rec.append("faithfulness")
    return rec or ["output", "helpfulness"]


def _infer_categories(desc: str, tools: list[str]) -> list[str]:
    cats = ["basic_functionality"] + (["tool_usage"] if tools else [])
    dl = desc.lower()
    if any(w in dl for w in ("search", "query", "find")): cats.append("information_retrieval")
    if any(w in dl for w in ("create", "generate", "write")): cats.append("content_generation")
    return cats + ["edge_cases", "error_handling"]


def _fallback_cases(state: SOPState, n: int) -> list[dict[str, Any]]:
    cats = state.eval_plan.get("test_categories", ["general"])
    return [{"id": f"c{i}", "name": f"{cats[i%len(cats)]}-{i}",
             "input": f"Test {i}: {state.agent_description[:40]}",
             "metadata": {"category": cats[i % len(cats)]}}
            for i in range(n)]
