"""Typed operational MCP tools for the Evals brick."""
from __future__ import annotations

from typing import Any, Callable, TYPE_CHECKING

from factory.mcp_utils.interface import ToolResult, get_service, operational

from .contracts.operational import (
    AddCaseInput, AddCaseOutput, CreateSuiteInput, CreateSuiteOutput,
    DeleteSuiteInput, DeleteSuiteOutput, PersistScoreInput, PersistScoreOutput,
)
from ..runtime.ports import EvalCase, EvalSuite

if TYPE_CHECKING:
    from ..runtime.runtime import EvalsRuntime


def register(mcp: Any, get_runtime: Callable[[], "EvalsRuntime"]) -> None:
    """Register operational Evals tools with flat typed ingress."""

    @mcp.tool()
    @operational(input_model=CreateSuiteInput, output_model=CreateSuiteOutput)
    def evals_create_suite(suite_id: str, name: str, description: str = "", cases: list[dict[str, Any]] | None = None) -> ToolResult[CreateSuiteOutput]:
        eval_cases = [EvalCase(id=item.get("id", ""), name=item.get("name", ""), input=item.get("input", {}), expected=item.get("expected"), metadata=item.get("metadata", {})) for item in (cases or [])]
        suite = get_runtime().get_runner().create_suite(EvalSuite(id=suite_id, name=name, description=description, cases=eval_cases))
        return CreateSuiteOutput(id=suite.id, name=suite.name, case_count=len(suite.cases))

    @mcp.tool()
    @operational(input_model=DeleteSuiteInput, output_model=DeleteSuiteOutput)
    def evals_delete_suite(suite_id: str) -> ToolResult[DeleteSuiteOutput]:
        suite = get_runtime().get_runner().get_suite(suite_id)
        if not suite:
            return DeleteSuiteOutput(deleted=False, error=f"Suite not found: {suite_id}")
        return DeleteSuiteOutput(deleted=False, error="Deletion not supported by current backend", suite_id=suite_id)

    @mcp.tool()
    @operational(input_model=AddCaseInput, output_model=AddCaseOutput)
    def evals_add_case(suite_id: str, case_id: str, name: str, input_data: dict[str, Any], expected: dict[str, Any] | None = None, metadata: dict[str, Any] | None = None) -> ToolResult[AddCaseOutput]:
        suite = get_runtime().get_runner().get_suite(suite_id)
        if not suite:
            return AddCaseOutput(added=False, error=f"Suite not found: {suite_id}")
        suite.cases.append(EvalCase(id=case_id, name=name, input=input_data, expected=expected, metadata=metadata or {}))
        return AddCaseOutput(added=True, suite_id=suite_id, case_id=case_id, total_cases=len(suite.cases))

    @mcp.tool()
    @operational(input_model=PersistScoreInput, output_model=PersistScoreOutput)
    def evals_persist_score(run_id: str, workflow_type: str, target_app: str, vuln_class: str, scoring: dict[str, Any], domain_class: str = "", source: str = "experiment") -> ToolResult[PersistScoreOutput]:
        from ..runtime._persist_score import persist_score_result
        invoker = get_service("tool_invoker")
        if invoker is None:
            return PersistScoreOutput(persisted=False, reason="no tool_invoker")
        persisted = persist_score_result(invoker, run_id, workflow_type, target_app, vuln_class, scoring, domain_class=domain_class, source=source)
        return PersistScoreOutput(persisted=persisted, doc_id=f"eval-score-{run_id}" if run_id else "")
