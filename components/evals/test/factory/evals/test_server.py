"""Tests for evals MCP server."""

import asyncio
import tempfile
import time
from pathlib import Path
from typing import get_type_hints

import pytest
from factory.mcp_utils.runtime.tool_catalog import ToolCatalog
from pydantic import BaseModel

from factory.mcp_utils.interface import ToolResult

from factory.evals.server import get_mcp_server
from factory.evals.runtime.adapters import run_results_store
from factory.evals.runtime.runtime import reset_runtime, get_runtime


class TestMCPContract:
    """Tests for MCP contract compliance."""

    def setup_method(self) -> None:
        reset_runtime()

    def teardown_method(self) -> None:
        reset_runtime()

    def test_mcp_server_created(self) -> None:
        """Should have a native ToolCatalog instance."""
        assert isinstance(get_mcp_server(), ToolCatalog)
        assert get_mcp_server().name == "factory-evals"

    def test_contract_tools_registered(self) -> None:
        """Should have contract tools registered."""
        tool_names = [t.name for t in asyncio.run(get_mcp_server().list_tools())]
        assert "get_capabilities" in tool_names
        assert "health_check" in tool_names
        assert "describe_config_schema" in tool_names

    def test_operational_tools_registered(self) -> None:
        """Should have operational tools registered."""
        tool_names = [t.name for t in asyncio.run(get_mcp_server().list_tools())]
        assert "evals_create_suite" in tool_names
        assert "evals_get_suite" in tool_names
        assert "evals_list_suites" in tool_names


class TestEvalsRuntime:
    """Tests for evals runtime integration."""

    def setup_method(self) -> None:
        reset_runtime()

    def teardown_method(self) -> None:
        reset_runtime()

    def test_runtime_available(self) -> None:
        """Should have runtime available."""
        runtime = get_runtime()
        assert runtime is not None

    def test_runtime_health_check(self) -> None:
        """Should return health status."""
        runtime = get_runtime()
        health = runtime.health_check()
        assert isinstance(health, dict)


class TestDashboardViewTools:
    """Tests for evals dashboard summary and regression view tools."""

    def setup_method(self) -> None:
        reset_runtime()

    def teardown_method(self) -> None:
        reset_runtime()

    def test_dashboard_tools_registered(self) -> None:
        """Dashboard-specific tools should be exposed by the MCP server."""
        tool_names = [t.name for t in asyncio.run(get_mcp_server().list_tools())]
        assert "evals_get_dashboard_summary" in tool_names
        assert "evals_get_run_regression" in tool_names
        assert "evals_get_experiment_config_cases" in tool_names
        assert "evals_get_failure_clusters" in tool_names
        assert "evals_get_views" in tool_names

    def test_dashboard_summary_groups_experiments_and_regressions(self) -> None:
        """Summary tool should aggregate experiment families and flag regressions.

        The experiment-serialization subsystem (save/load/list saved
        experiments) was removed by the native-MCP-v2 migration
        (commit a4437ac0); saved-config fixtures are no longer seedable here,
        so this only exercises the run-doc-store aggregation path.
        """
        original_dir = run_results_store._RUNS_DIR
        try:
            with tempfile.TemporaryDirectory() as td:
                run_results_store._RUNS_DIR = Path(td) / "eval_runs"

                # Populate doc store via a fake invoker (v7imt.1 Option C)
                from factory.mcp_utils.registry import set_service, get_service
                _docs: dict[str, dict] = {}

                def _artifact(data):
                    from factory.evals.runtime.run_record_contract import build_record

                    return build_record(
                        run_id=data["run_id"], record_kind="evaluation_run",
                        terminal_state="completed", timestamp=data["timestamp"],
                        payload={key: value for key, value in data.items() if key not in {"run_id", "timestamp"}},
                    )

                def _fake_invoker(tool_name: str, **kwargs):
                    if tool_name == "storage_doc_insert":
                        key = f"{kwargs['collection']}:{kwargs['doc_id']}"
                        _docs[key] = {
                            "id": kwargs["doc_id"], "collection": kwargs["collection"],
                            "data": kwargs["data"],
                        }
                        return {"id": kwargs["doc_id"]}
                    if tool_name == "storage_doc_find":
                        coll = kwargs["collection"]
                        docs = [v for k, v in _docs.items() if k.startswith(f"{coll}:")]
                        return {"documents": docs[:kwargs.get("limit", 100)]}
                    if tool_name == "storage_doc_get":
                        key = f"{kwargs['collection']}:{kwargs['doc_id']}"
                        return _docs.get(key, {"error": "not_found"})
                    return {}

                def _insert_run(data):
                    doc_id, record = _artifact(data)
                    _fake_invoker(
                        "storage_doc_insert", collection="eval_results",
                        doc_id=doc_id, data=record,
                    )

                prev_invoker = get_service("tool_invoker")
                set_service("tool_invoker", _fake_invoker)

                _insert_run({
                    "run_id": "run-a1", "experiment_name": "exp-a",
                    "timestamp": "2026-07-01T01:00:00Z", "verdict": "PASS", "source": "experiment",
                    "pass_rate": 1.0, "avg_score": 1.0, "total_cases": 1, "passed_cases": 1, "failed_cases": 0,
                    "evaluators_used": ["judge-a"], "case_results": [{"case_name": "c1", "passed": True, "score": 1.0, "reason": "ok"}],
                    "case_scores": [1.0], "agent": {"model_id": "model-a"}, "summary": {},
                })
                latest_a = "run-a2"
                _insert_run({
                    "run_id": "run-a2", "experiment_name": "exp-a",
                    "timestamp": "2026-07-01T02:00:00Z", "verdict": "FAIL", "source": "experiment",
                    "pass_rate": 0.0, "avg_score": 0.2, "total_cases": 1, "passed_cases": 0, "failed_cases": 1,
                    "evaluators_used": ["judge-a"], "case_results": [{"case_name": "c1", "passed": False, "score": 0.2, "reason": "bad"}],
                    "case_scores": [0.2], "agent": {"model_id": "model-a"}, "summary": {},
                })
                _insert_run({
                    "run_id": "run-b1", "experiment_name": "exp-b",
                    "timestamp": "2026-07-01T03:00:00Z", "verdict": "FAIL", "source": "experiment",
                    "pass_rate": 0.0, "avg_score": 0.15, "total_cases": 2, "passed_cases": 0, "failed_cases": 2,
                    "evaluators_used": ["judge-b"],
                    "case_results": [
                        {"case_name": "c1", "passed": False, "score": 0.1, "reason": "timeout", "input_snippet": "foo"},
                        {"case_name": "c1", "passed": False, "score": 0.2, "reason": "bad schema", "input_snippet": "bar"},
                    ],
                    "case_scores": [0.1, 0.2], "agent": {"model_id": "model-b"}, "summary": {},
                })

                summary_tool = asyncio.run(get_mcp_server().get_tool("evals_get_dashboard_summary"))
                regression_tool = asyncio.run(get_mcp_server().get_tool("evals_get_run_regression"))
                config_tool = asyncio.run(get_mcp_server().get_tool("evals_get_experiment_config_cases"))
                clusters_tool = asyncio.run(get_mcp_server().get_tool("evals_get_failure_clusters"))
                views_tool = asyncio.run(get_mcp_server().get_tool("evals_get_views"))

                summary_result = summary_tool.fn()
                regression_result = regression_tool.fn(run_id=latest_a)
                saved_missing_result = config_tool.fn(filename="")
                views_result = views_tool.fn()
                assert summary_result.schema_version == "v1" and summary_result.ok
                assert regression_result.schema_version == "v1" and regression_result.ok
                assert saved_missing_result.schema_version == "v1" and saved_missing_result.ok
                assert views_result.schema_version == "v1" and views_result.ok
                summary = summary_result.data
                regression = regression_result.data
                saved_missing = saved_missing_result.data
                views = views_result.data
                assert summary is not None and regression is not None
                assert saved_missing is not None and views is not None
                exp_b = next(item for item in summary.experiments if item.experiment_name == "exp-b")
                clusters_result = clusters_tool.fn(run_id=exp_b.latest_run_id)
                assert clusters_result.schema_version == "v1" and clusters_result.ok
                clusters = clusters_result.data
                assert clusters is not None

                assert summary.overview.runs == 3
                assert summary.overview.experiments == 2
                assert summary.overview.saved_configs == 0
                assert summary.overview.regressions == 1
                assert summary.experiments[0].experiment_name == "exp-a"
                assert summary.experiments[0].regression_state == "regressed"
                assert all(item.config_status == "ad_hoc" for item in summary.experiments)
                assert regression.regressed is True
                assert saved_missing.status == "missing"
                assert clusters.count == 1
                assert clusters.clusters[0].name == "c1"
                assert clusters.clusters[0].failures == 2
                component_ids = [component["id"] for component in views.views[0].components]
                assert "evals-recent-trend" in component_ids
                assert "evals-experiment-health" in component_ids
                assert "evals-run-results" in component_ids

                set_service("tool_invoker", prev_invoker)
        finally:
            run_results_store._RUNS_DIR = original_dir


class TestSeedDefaultsTool:
    """Direct typed-envelope tests for the idempotent default seed."""

    def test_seed_defaults_returns_idempotent_v1_envelopes(self) -> None:
        tool = asyncio.run(get_mcp_server().get_tool("evals_seed_defaults"))

        first = tool.fn()
        second = tool.fn()

        assert first.schema_version == second.schema_version == "v1"
        assert first.ok and second.ok
        assert first.data is not None and second.data is not None
        assert len(first.data.created) + len(first.data.skipped) == first.data.total
        assert second.data.created == []
        assert len(second.data.skipped) == second.data.total


class TestViewFailureEnvelopes:
    """Legacy view error payloads are normalized at the typed boundary."""

    def test_missing_run_uses_failed_v1_envelope(self) -> None:
        regression = asyncio.run(get_mcp_server().get_tool("evals_get_run_regression"))
        clusters = asyncio.run(get_mcp_server().get_tool("evals_get_failure_clusters"))

        for result in (
            regression.fn(run_id="missing-run"),
            clusters.fn(run_id="missing-run"),
        ):
            assert result.schema_version == "v1"
            assert not result.ok
            assert result.data is None
            assert result.error == "Run not found: missing-run"


def test_all_fifty_one_public_tools_publish_typed_boundaries() -> None:
    """Every registered Evals tool must expose concrete local Pydantic boundaries.

    Tool count is 51 after adding Evals-owned immutable development review recording;
    the prior 50-tool baseline restored the
    Strands experiment/simulation/serialization/tool-chaos tool group as
    native MCP v2 tools (evals_run_experiment, evals_save_experiment,
    evals_load_experiment, evals_list_saved_experiments,
    evals_run_simulation, evals_run_tool_chaos, evals_generate_experiment,
    evals_list_evaluators, evals_list_run_results, evals_get_run_result).
    Commit a4437ac0 (native MCP v2 migration) had dropped them to 40.
    """
    tools = asyncio.run(get_mcp_server().list_tools())
    assert len(tools) == 51
    for tool in tools:
        input_model = getattr(tool.fn, "_mcp_input_model", None)
        output_model = getattr(tool.fn, "_mcp_output_model", None)
        assert isinstance(input_model, type) and issubclass(input_model, BaseModel), tool.name
        assert isinstance(output_model, type) and issubclass(output_model, BaseModel), tool.name
        assert input_model.__module__.startswith("factory.evals."), tool.name
        assert output_model.__module__.startswith("factory.evals."), tool.name
        assert input_model.model_config.get("extra") == "forbid", tool.name
        assert output_model.model_config.get("extra") == "forbid", tool.name
        return_model = get_type_hints(tool.fn)["return"]
        assert issubclass(return_model, ToolResult), tool.name
        assert return_model.__pydantic_generic_metadata__["args"] == (output_model,), tool.name
