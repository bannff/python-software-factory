"""UI Explorer adapter - executes UI scenarios via Chrome DevTools MCP."""

from __future__ import annotations

import time
import uuid
from datetime import datetime
from typing import Any, Callable

from ..ports import EvalCase, EvalResult, EvalSuite, EvalRun, EvalMetrics, EvalHealth
from ..ui import UIScenario, UIFinding, FindingSeverity, UIReporter


class UIExplorerRunner:
    """Evaluation runner for UI exploration via Chrome DevTools MCP."""

    def __init__(self, **kwargs: Any) -> None:
        self._scenarios: dict[str, UIScenario] = {}
        self._runs: dict[str, EvalRun] = {}
        self._findings: dict[str, list[UIFinding]] = {}
        self._reporters: list[UIReporter] = []

    def add_reporter(self, reporter: UIReporter) -> None:
        """Add a reporter for findings."""
        self._reporters.append(reporter)

    def create_scenario(self, scenario: UIScenario) -> UIScenario:
        """Register a UI exploration scenario."""
        self._scenarios[scenario.id] = scenario
        return scenario

    def get_scenario(self, scenario_id: str) -> UIScenario | None:
        """Get a scenario by ID."""
        return self._scenarios.get(scenario_id)

    def list_scenarios(self) -> list[UIScenario]:
        """List all registered scenarios."""
        return list(self._scenarios.values())

    def create_suite(self, suite: EvalSuite) -> EvalSuite:
        """Create eval suite (for compatibility with EvalRunner protocol)."""
        # Convert EvalCases to UIScenarios if needed
        return suite

    def get_suite(self, suite_id: str) -> EvalSuite | None:
        """Get suite by ID."""
        return None  # UI Explorer uses scenarios, not suites

    def list_suites(self) -> list[EvalSuite]:
        """List suites."""
        return []

    def run_suite(
        self,
        suite_id: str,
        agent_fn: Callable[[dict[str, Any]], dict[str, Any]],
        scorer_fn: Callable[[EvalCase, dict[str, Any]], EvalResult] | None = None,
    ) -> EvalRun:
        """Run suite (compatibility method)."""
        raise NotImplementedError("Use run_scenario for UI exploration")

    def run_scenario(
        self,
        scenario_id: str,
        context: dict[str, Any],
    ) -> EvalRun:
        """Process results from a UI exploration run.

        The actual exploration is done by the agent using Chrome DevTools.
        This method processes the collected context and runs assertions.

        Args:
            scenario_id: ID of the scenario that was run
            context: Collected data including:
                - console_messages: From list_console_messages
                - network_requests: From list_network_requests
                - snapshot: From take_snapshot
                - performance: From performance trace
                - screenshots: Paths to any screenshots taken

        Returns:
            EvalRun with results from assertions
        """
        scenario = self.get_scenario(scenario_id)
        if not scenario:
            raise ValueError(f"Scenario not found: {scenario_id}")

        run = EvalRun(
            id=str(uuid.uuid4()),
            suite_id=scenario_id,
            started_at=datetime.now(),
            status="running",
        )

        findings: list[UIFinding] = []

        # Run each assertion
        for assertion in scenario.assertions:
            start = time.perf_counter()
            result = assertion.check(context)
            duration = (time.perf_counter() - start) * 1000

            eval_result = EvalResult(
                case_id=assertion.assertion_type,
                passed=result.passed,
                score=1.0 if result.passed else 0.0,
                actual=result.details,
                duration_ms=duration,
                error=None if result.passed else result.message,
            )
            run.results.append(eval_result)

            # Create finding for failures
            if not result.passed:
                finding = UIFinding(
                    id=str(uuid.uuid4()),
                    scenario_id=scenario_id,
                    severity=self._severity_from_assertion(assertion.assertion_type),
                    title=f"{assertion.assertion_type} failed",
                    description=result.message,
                    assertion_type=assertion.assertion_type,
                    route=scenario.route,
                    details=result.details,
                )
                findings.append(finding)

        # Store findings
        self._findings[run.id] = findings

        # Report findings
        for reporter in self._reporters:
            reporter.report(findings)

        run.completed_at = datetime.now()
        run.status = "completed"
        run.summary = {
            "total_assertions": len(scenario.assertions),
            "passed": sum(1 for r in run.results if r.passed),
            "failed": sum(1 for r in run.results if not r.passed),
            "findings": len(findings),
        }

        self._runs[run.id] = run
        return run

    def _severity_from_assertion(self, assertion_type: str) -> FindingSeverity:
        """Map assertion type to finding severity."""
        severity_map = {
            "console_clean": FindingSeverity.HIGH,
            "network_ok": FindingSeverity.HIGH,
            "a11y_valid": FindingSeverity.MEDIUM,
            "performance_budget": FindingSeverity.MEDIUM,
            "element_exists": FindingSeverity.LOW,
        }
        return severity_map.get(assertion_type, FindingSeverity.INFO)

    def get_run(self, run_id: str) -> EvalRun | None:
        """Get a run by ID."""
        return self._runs.get(run_id)

    def list_runs(self, suite_id: str | None = None) -> list[EvalRun]:
        """List runs, optionally filtered by scenario."""
        runs = list(self._runs.values())
        if suite_id:
            runs = [r for r in runs if r.suite_id == suite_id]
        return runs

    def get_findings(self, run_id: str) -> list[UIFinding]:
        """Get findings from a run."""
        return self._findings.get(run_id, [])

    def compute_metrics(self, run: EvalRun) -> EvalMetrics:
        """Compute metrics from a run."""
        if not run.results:
            return EvalMetrics()

        passed = sum(1 for r in run.results if r.passed)
        total = len(run.results)

        return EvalMetrics(
            total_cases=total,
            passed=passed,
            failed=total - passed,
            pass_rate=passed / total if total > 0 else 0.0,
            avg_score=passed / total if total > 0 else 0.0,
        )

    def health_check(self) -> EvalHealth:
        """Check runner health."""
        return EvalHealth(
            healthy=True,
            backend="ui_explorer",
            message="UI Explorer ready. Requires Chrome DevTools MCP for execution.",
        )
