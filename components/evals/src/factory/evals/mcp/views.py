"""UIView definitions for Evals brick — result-first layout."""
from __future__ import annotations

from typing import Any
from factory.mcp_utils.interface import ToolResult, deterministic, fail

from .view_seed_dtos import (
    DashboardSummaryOutput,
    ExperimentConfigCasesOutput,
    FailureClustersOutput,
    ViewFilenameInput,
    ViewRunIdInput,
    ViewSeedEmptyInput,
    ViewsOutput,
    RunRegressionOutput,
)


def register(mcp: Any) -> None:
    """Register Evals view definitions."""

    @mcp.tool()
    @deterministic(input_model=ViewSeedEmptyInput, output_model=DashboardSummaryOutput)
    def evals_get_dashboard_summary() -> ToolResult[DashboardSummaryOutput]:
        """Return aggregate dashboard data for evals views."""
        from ..runtime.adapters.doc_store_reader import list_runs

        return DashboardSummaryOutput(**_build_dashboard_summary(list_runs(), []))

    @mcp.tool()
    @deterministic(input_model=ViewRunIdInput, output_model=RunRegressionOutput)
    def evals_get_run_regression(run_id: str) -> ToolResult[RunRegressionOutput]:
        """Return regression signal for a specific run against its predecessor."""
        from ..runtime.adapters.doc_store_reader import list_runs

        for run in list_runs():
            if run.get("run_id") == run_id:
                return RunRegressionOutput(
                    regressed=run.get("regression_state") == "regressed",
                    regression_state=run.get("regression_state", "baseline"),
                    pass_rate_delta=run.get("pass_rate_delta", 0.0),
                    avg_score_delta=run.get("avg_score_delta", 0.0),
                    previous_run_id=run.get("previous_run_id"),
                )
        return fail(f"Run not found: {run_id}")

    @mcp.tool()
    @deterministic(input_model=ViewFilenameInput, output_model=ExperimentConfigCasesOutput)
    def evals_get_experiment_config_cases(
        filename: str = "",
    ) -> ToolResult[ExperimentConfigCasesOutput]:
        """Return saved config cases for an experiment, or an empty payload when absent."""
        if not filename:
            return ExperimentConfigCasesOutput(
                status="missing",
                message="No saved config is linked to this experiment yet.",
            )
        return ExperimentConfigCasesOutput(
            status="missing",
            message=f"Saved experiment configs are unavailable: {filename}",
        )

    @mcp.tool()
    @deterministic(input_model=ViewRunIdInput, output_model=FailureClustersOutput)
    def evals_get_failure_clusters(run_id: str) -> ToolResult[FailureClustersOutput]:
        """Cluster recurring failures for an experiment family anchored at a run."""
        from ..runtime.adapters.doc_store_reader import get_run, list_runs

        runs = list_runs()
        anchor = next((run for run in runs if run.get("run_id") == run_id), None)
        if anchor is None:
            return fail(f"Run not found: {run_id}")

        experiment_name = anchor.get("experiment_name", "")
        family_runs = [run for run in runs if run.get("experiment_name") == experiment_name]
        clusters: dict[str, dict[str, Any]] = {}

        for family_run in family_runs:
            record = get_run(str(family_run.get("run_id", "")))
            if not record:
                continue
            for case in record.get("case_results", []):
                if case.get("passed"):
                    continue
                case_name = str(case.get("case_name") or "unnamed-case")
                cluster = clusters.setdefault(case_name, {
                    "name": case_name, "status": "recurring failure", "failures": 0,
                    "runs": [], "latest_reason": "", "avg_score": 0.0, "examples": [],
                })
                cluster["failures"] += 1
                cluster["runs"].append(record.get("run_id", ""))
                cluster["latest_reason"] = case.get("reason", "")
                cluster["examples"].append(case.get("input_snippet", ""))
                cluster["avg_score"] += float(case.get("score", 0.0) or 0.0)

        ordered = []
        for cluster in clusters.values():
            failures = int(cluster["failures"])
            cluster["avg_score"] = round(cluster["avg_score"] / failures, 3) if failures else 0.0
            cluster["reason"] = (
                f"Failed {failures} time(s) across {len(set(cluster['runs']))} run(s). "
                f"Latest: {cluster['latest_reason'] or 'No reason recorded.'}"
            )
            cluster["input_snippet"] = next(
                (example for example in cluster["examples"] if example), "",
            )
            ordered.append(cluster)

        ordered.sort(key=lambda item: (-int(item["failures"]), float(item["avg_score"])))
        return FailureClustersOutput(
            experiment_name=experiment_name, clusters=ordered, count=len(ordered),
        )

    @mcp.tool()
    @deterministic(input_model=ViewSeedEmptyInput, output_model=ViewsOutput)
    def evals_get_views() -> ToolResult[ViewsOutput]:
        """Return UIView definitions for the Evals brick."""
        return ViewsOutput(views=[{
            "id": "evals-dashboard",
            "name": "Evaluations",
            "brick": "evals",
            "icon": "🧪",
            "layout": {"type": "flex", "direction": "column"},
            "components": [
                _recent_trend_chart(),
                _experiment_health(),
                _run_results(),
                _evaluators_catalog(),
                _sop_list(),
            ],
            "metadata": {
                "description": "Agent quality benchmarking with LLMAJ evaluators",
                "nav_label": "Evals",
                "nav_order": 15,
            },
        }])


def _build_dashboard_summary(
    runs: list[dict[str, Any]],
    saved_experiments: list[dict[str, Any]],
) -> dict[str, Any]:
    """Aggregate recent eval activity into dashboard-friendly structures."""
    saved_by_stem = {
        str(item.get("filename", "")).removesuffix(".json"): item
        for item in saved_experiments
    }
    latest_by_experiment: dict[str, dict[str, Any]] = {}
    histories: dict[str, list[dict[str, Any]]] = {}

    for run in runs:
        experiment_name = str(run.get("experiment_name", ""))
        histories.setdefault(experiment_name, []).append(run)
        latest_by_experiment.setdefault(experiment_name, run)

    experiments = []
    for experiment_name, latest in latest_by_experiment.items():
        history = histories.get(experiment_name, [])
        saved = saved_by_stem.pop(experiment_name, None)
        avg_pass_rate = round(
            sum(float(item.get("pass_rate", 0.0)) for item in history) / len(history),
            3,
        ) if history else 0.0
        experiments.append({
            "experiment_name": experiment_name,
            "runs": len(history),
            "latest_verdict": latest.get("verdict", "—"),
            "latest_pass_rate": latest.get("pass_rate", 0.0),
            "avg_pass_rate": avg_pass_rate,
            "latest_avg_score": latest.get("avg_score", 0.0),
            "latest_timestamp": latest.get("timestamp", ""),
            "latest_status": latest.get("completion_status", "completed_time_unavailable"),
            "latest_run_id": latest.get("run_id", ""),
            "latest_failed_cases": latest.get("failed_cases", 0),
            "evaluators_used": latest.get("evaluators_used", []),
            "agent": latest.get("agent", {}),
            "trend_direction": latest.get("trend_direction", "flat"),
            "pass_rate_delta": latest.get("pass_rate_delta", 0.0),
            "regression_state": latest.get("regression_state", "baseline"),
            "recent_pass_rates": [item.get("pass_rate", 0.0) for item in reversed(history[:8])],
            "saved_filename": saved.get("filename", "") if saved else "",
            "saved_cases": saved.get("cases", 0) if saved else 0,
            "saved_path": saved.get("path", "") if saved else "",
            "config_status": "saved" if saved else "ad_hoc",
        })

    for stem, saved in saved_by_stem.items():
        experiments.append({
            "experiment_name": stem,
            "runs": 0,
            "latest_verdict": "NOT_RUN",
            "latest_pass_rate": 0.0,
            "avg_pass_rate": 0.0,
            "latest_avg_score": 0.0,
            "latest_timestamp": "",
            "latest_status": "not_run",
            "latest_run_id": "",
            "latest_failed_cases": 0,
            "evaluators_used": [],
            "agent": {},
            "trend_direction": "flat",
            "pass_rate_delta": 0.0,
            "regression_state": "baseline",
            "recent_pass_rates": [],
            "saved_filename": saved.get("filename", ""),
            "saved_cases": saved.get("cases", 0),
            "saved_path": saved.get("path", ""),
            "config_status": "saved_only",
        })

    # Newest-first within each group: stable sort by group keys after
    # pre-sorting by timestamp DESC. Python sort is stable, so order holds.
    experiments.sort(key=lambda item: item.get("latest_timestamp", ""), reverse=True)
    experiments.sort(
        key=lambda item: (
            item.get("regression_state") != "regressed",
            item.get("config_status") == "saved_only",
            item.get("latest_verdict") == "PASS",
        ),
    )

    series = [
        {
            "label": str(run.get("experiment_name", "run"))[:18],
            "value": run.get("pass_rate", 0.0),
            "avg_score": run.get("avg_score", 0.0),
            "timestamp": run.get("timestamp", ""),
        }
        for run in reversed(runs[:10])
    ]

    total_runs = len(runs)
    failing_runs = sum(1 for run in runs if run.get("verdict") == "FAIL")
    regressed_experiments = sum(
        1 for item in experiments if item.get("regression_state") == "regressed"
    )
    avg_pass_rate = round(
        sum(float(run.get("pass_rate", 0.0)) for run in runs) / total_runs,
        3,
    ) if runs else 0.0

    return {
        "overview": {
            "runs": total_runs,
            "experiments": len(experiments),
            "saved_configs": len(saved_experiments),
            "failing_runs": failing_runs,
            "regressions": regressed_experiments,
            "avg_pass_rate": avg_pass_rate,
        },
        "series": series,
        "experiments": experiments,
    }


def _recent_trend_chart() -> dict[str, Any]:
    """Recent run pass-rate trend for quick visual scanning."""
    return {
        "id": "evals-recent-trend",
        "type": "chart",
        "props": {
            "title": "Recent Run Pass Rate",
            "data_tool": "evals_get_dashboard_summary",
            "xKey": "label",
            "yKey": "value",
            "empty_state": "Run an experiment to build a visible pass-rate trend.",
            "className": "mb-3",
        },
    }


def _experiment_health() -> dict[str, Any]:
    """Experiment-level grouped health summary."""
    return {
        "id": "evals-experiment-health",
        "type": "item_list",
        "props": {
            "data_tool": "evals_get_dashboard_summary",
            "data_path": "$.experiments",
            "item_key": "experiment_name",
            "empty_icon": "beaker",
            "empty_message": "No experiment families yet. Run an eval to build history.",
            "header": {
                "icon": "chart-bar",
                "stats_tool": "evals_get_dashboard_summary",
                "stats_map": {
                    "experiments": "$.overview.experiments",
                    "configs": "$.overview.saved_configs",
                    "regressions": "$.overview.regressions",
                },
            },
            "filters": {
                "field": "regression_state",
                "values": ["regressed", "improved", "steady", "baseline"],
                "colors": {
                    "regressed": "red",
                    "improved": "emerald",
                    "steady": "blue",
                    "baseline": "gray",
                },
                "show_counts": True,
            },
            "item_layout": {
                "status_dot": {
                    "value_path": "$.latest_verdict",
                    "states": {"FAIL": "red", "PASS": "emerald", "NOT_RUN": "gray"},
                },
                "title": "$.experiment_name",
                "subtitle": "$.saved_filename",
                "badge": {
                    "field": "regression_state",
                    "color_map": "filters.colors",
                    "suffix": "",
                },
                "value": {
                    "path": "$.latest_pass_rate",
                    "format": "percent",
                },
                "trend": {
                    "direction": "$.trend_direction",
                    "change_pct": "$.pass_rate_delta",
                    "positive_is_good": True,
                },
            },
            "detail": {
                "sparkline": {
                    "data_path": "$.recent_pass_rates",
                    "color": "indigo",
                    "height": 28,
                    "max_points": 8,
                    "variant": "line",
                },
                "metadata": [
                    {"label": "Latest Verdict", "path": "$.latest_verdict", "zone": "config"},
                    {"label": "Completion", "path": "$.latest_status", "zone": "identity"},
                    {"label": "Config", "path": "$.saved_filename", "zone": "config"},
                    {"label": "Evaluators", "path": "$.evaluators_used", "render_as": "pills", "zone": "config"},
                    {"label": "Model", "path": "$.agent.model_id", "render_as": "model_chip", "zone": "config"},
                    {"label": "Runs", "path": "$.runs", "zone": "identity"},
                    {"label": "Saved Cases", "path": "$.saved_cases", "zone": "identity"},
                    {"label": "Avg Pass", "path": "$.avg_pass_rate", "render_as": "score", "zone": "identity"},
                    {"label": "Latest Run", "path": "$.latest_run_id", "render_as": "copy_id", "zone": "identity"},
                ],
                "tabs": [
                    {
                        "id": "config",
                        "label": "Saved Config",
                        "tool": "evals_get_experiment_config_cases",
                        "args": {"filename": "$.saved_filename"},
                        "data_path": "$.cases",
                        "empty_message": "No saved config is linked to this experiment yet.",
                        "render_as": "list",
                    },
                ],
            },
        },
    }


def _run_results() -> dict[str, Any]:
    """Run results — primary section, shows actual scores and verdicts."""
    return {
        "id": "evals-run-results",
        "type": "item_list",
        "props": {
            "data_tool": "evals_list_run_results",
            "data_path": "$.runs",
            "item_key": "run_id",
            "empty_icon": "beaker",
            "empty_message": (
                "No eval runs yet. Use evals_run_experiment to run an"
                " experiment and see scores, verdicts, and reasons here."
            ),
            "header": {
                "icon": "beaker",
                "stats_tool": "evals_get_dashboard_summary",
                "stats_map": {
                    "runs": "$.overview.runs",
                    "families": "$.overview.experiments",
                    "failures": "$.overview.failing_runs",
                },
            },
            "filters": {
                "field": "verdict",
                "values": ["PASS", "FAIL"],
                "colors": {"PASS": "emerald", "FAIL": "red"},
                "show_counts": True,
            },
            "item_layout": {
                "status_dot": {
                    "value_path": "$.verdict",
                    "states": {"PASS": "emerald", "FAIL": "red"},
                },
                "title": "$.experiment_name",
                "subtitle": "$.agent.model_id",
                "badge": {
                    "field": "verdict",
                    "color_map": "filters.colors",
                    "suffix": "",
                },
                "value": {
                    "path": "$.pass_rate",
                    "format": "percent",
                },
                "trend": {
                    "direction": "$.trend_direction",
                    "change_pct": "$.pass_rate_delta",
                    "positive_is_good": True,
                },
            },
            "detail": {
                "sparkline": {
                    "data_path": "$.case_scores",
                    "color": "indigo",
                    "height": 28,
                    "max_points": 20,
                    "variant": "bar",
                },
                "metadata": [
                    {"label": "Model", "path": "$.agent.model_id", "render_as": "model_chip", "zone": "config"},
                    {"label": "System Prompt", "path": "$.agent.system_prompt_snippet", "render_as": "popover", "zone": "config"},
                    {"label": "Judges", "path": "$.evaluators_used", "render_as": "pills", "zone": "config"},
                    {"label": "Cases", "path": "$.total_cases", "zone": "identity"},
                    {"label": "Failures", "path": "$.failed_cases", "zone": "identity"},
                    {"label": "Avg Score", "path": "$.avg_score", "render_as": "score", "zone": "identity"},
                    {"label": "Run ID", "path": "$.run_id", "render_as": "copy_id", "zone": "identity"},
                    {"label": "Timestamp", "path": "$.timestamp", "render_as": "relative_time", "zone": "identity"},
                ],
                "tabs": [
                    {
                        "id": "cases", "label": "Case Results",
                        "tool": "evals_get_run_result",
                        "args": {"run_id": "$.run_id"},
                        "render_as": "list",
                    },
                    {
                        "id": "regression", "label": "Regression",
                        "tool": "evals_get_run_regression",
                        "args": {"run_id": "$.run_id"},
                        "render_as": "alert",
                        "alert_props": {
                            "intent_field": "regressed",
                            "intent_map": {"true": "warning", "false": "success"},
                        },
                    },
                    {
                        "id": "clusters", "label": "Failure Clusters",
                        "tool": "evals_get_failure_clusters",
                        "args": {"run_id": "$.run_id"},
                        "data_path": "$.clusters",
                        "render_as": "list",
                    },
                ],
            },
        },
    }


def _evaluators_catalog() -> dict[str, Any]:
    """12 LLMAJ judges — reference with plain-English labels."""
    return {"id": "evals-evaluators", "type": "item_list", "props": {
        "data_tool": "evals_list_evaluators", "data_path": "$.evaluators",
        "item_key": "name", "empty_icon": "beaker",
        "empty_message": "No evaluators found.",
        "header": {"icon": "beaker", "stats_tool": "evals_list_evaluators",
                   "stats_map": {"evaluators": "$.count"}},
        "filters": {"field": "level",
                    "values": ["OUTPUT_LEVEL", "TRACE_LEVEL", "SESSION_LEVEL"],
                    "colors": {"OUTPUT_LEVEL": "purple", "TRACE_LEVEL": "blue",
                               "SESSION_LEVEL": "emerald"}, "show_counts": True},
        "item_layout": {"title": "$.name",
                        "badge": {"field": "level", "suffix": "",
                                  "color_map": "filters.colors"}},
        "detail": {"metadata": [
            {"label": "What it judges", "path": "$.description"},
            {"label": "Granularity", "path": "$.level"},
            {"label": "Needs custom rubric", "path": "$.requires_rubric"},
        ]},
    }}


def _sop_list() -> dict[str, Any]:
    """SOP sessions — Plan→Data→Eval→Report workflow tracker."""
    return {"id": "evals-sop-sessions", "type": "item_list", "props": {
        "data_tool": "evals_sop_list", "data_path": "$.sessions",
        "item_key": "id", "empty_icon": "clipboard-document-list",
        "empty_message": "No SOP sessions. Use evals_sop_plan to start.",
        "header": {"icon": "clipboard-document-list"},
        "filters": {"field": "phase",
                    "values": ["plan", "data", "eval", "report"],
                    "colors": {"plan": "gray", "data": "yellow",
                               "eval": "blue", "report": "emerald"},
                    "show_counts": True},
        "item_layout": {
            "status_dot": {"value_path": "$.phase",
                           "states": {"report": "emerald", "eval": "blue",
                                      "data": "yellow", "plan": "gray"}},
            "title": "$.description",
            "badge": {"field": "phase", "suffix": "", "color_map": "filters.colors"},
        },
        "detail": {"metadata": [
            {"label": "Session ID", "path": "$.id"},
            {"label": "Phase", "path": "$.phase"},
            {"label": "Agent", "path": "$.agent"},
        ]},
    }}
