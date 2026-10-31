"""Tests for evals runtime."""

import pytest

from factory.mcp_utils.runtime.tool_failure import SafeDiagnostic

from factory.evals.runtime.runtime import (
    EvalsRuntime,
    get_runtime,
    reset_runtime,
)
from factory.evals.runtime.ports import EvalCase, EvalSuite


class TestEvalsRuntime:
    """Tests for EvalsRuntime factory."""

    def setup_method(self) -> None:
        reset_runtime()

    def teardown_method(self) -> None:
        reset_runtime()

    def test_available_backends(self) -> None:
        """The framework-neutral and restored Strands backends are available."""
        assert EvalsRuntime.available_backends() == ["custom", "strands"]

    def test_get_runtime_singleton(self) -> None:
        """Should return same runtime instance."""
        r1 = get_runtime()
        r2 = get_runtime()
        assert r1 is r2

    def test_reset_runtime(self) -> None:
        """Should reset runtime instance."""
        r1 = get_runtime()
        reset_runtime()
        r2 = get_runtime()
        assert r1 is not r2

    def test_unknown_backend_raises(self) -> None:
        """Should raise for unknown backend."""
        runtime = EvalsRuntime()
        with pytest.raises(ValueError, match="Unknown evals backend"):
            runtime.get_runner("unknown")

    def test_unknown_backend_raises_safe_diagnostic(self) -> None:
        """Should raise SafeDiagnostic (not a bare ValueError) with the
        specific diagnostic message preserved, so the MCP boundary can log
        it verbatim instead of collapsing it into tool_execution_failed."""
        runtime = EvalsRuntime()
        with pytest.raises(SafeDiagnostic) as exc_info:
            runtime.get_runner("bogus")
        assert "Unknown evals backend: bogus" in str(exc_info.value)
        assert "Available: ['custom', 'strands']" in str(exc_info.value)

    def test_get_runner_custom(self) -> None:
        """Should create custom runner."""
        runtime = EvalsRuntime()
        runner = runtime.get_runner("custom")
        assert runner is not None

    def test_health_check_empty(self) -> None:
        """Should return empty health when no runners active."""
        runtime = EvalsRuntime()
        health = runtime.health_check()
        assert health == {}


class TestCustomRunner:
    """Tests for custom eval runner."""

    def setup_method(self) -> None:
        reset_runtime()

    def teardown_method(self) -> None:
        reset_runtime()

    def test_create_and_get_suite(self) -> None:
        """Should create and retrieve suite."""
        runtime = EvalsRuntime()
        runner = runtime.get_runner("custom")

        suite = EvalSuite(id="s1", name="Test Suite", cases=[])
        runner.create_suite(suite)

        result = runner.get_suite("s1")
        assert result is not None
        assert result.id == "s1"
        assert result.name == "Test Suite"

    def test_list_suites(self) -> None:
        """Should list all suites."""
        runtime = EvalsRuntime()
        runner = runtime.get_runner("custom")

        runner.create_suite(EvalSuite(id="s1", name="Suite 1", cases=[]))
        runner.create_suite(EvalSuite(id="s2", name="Suite 2", cases=[]))

        suites = runner.list_suites()
        assert len(suites) == 2

    def test_run_suite(self) -> None:
        """Should run suite against agent."""
        runtime = EvalsRuntime()
        runner = runtime.get_runner("custom")

        cases = [
            EvalCase(id="c1", name="Add", input={"a": 2, "b": 3}, expected={"result": 5}),
            EvalCase(id="c2", name="Mult", input={"a": 2, "b": 3}, expected={"result": 6}),
        ]
        runner.create_suite(EvalSuite(id="s1", name="Math", cases=cases))

        def agent(input: dict) -> dict:
            return {"result": input["a"] + input["b"]}

        run = runner.run_suite("s1", agent)
        assert run.status == "completed"
        assert len(run.results) == 2
        assert run.results[0].passed is True  # 2+3=5
        assert run.results[1].passed is False  # 2+3!=6

    def test_run_suite_with_custom_scorer(self) -> None:
        """Should use custom scorer."""
        runtime = EvalsRuntime()
        runner = runtime.get_runner("custom")

        from factory.evals.runtime.ports import EvalResult

        cases = [EvalCase(id="c1", name="Test", input={"x": 10}, expected={"x": 10})]
        runner.create_suite(EvalSuite(id="s1", name="Test", cases=cases))

        def agent(input: dict) -> dict:
            return {"x": input["x"] * 2}

        def scorer(case: EvalCase, actual: dict) -> EvalResult:
            # Custom: pass if actual is double expected
            passed = actual.get("x") == case.expected.get("x") * 2
            return EvalResult(case_id=case.id, passed=passed, score=1.0 if passed else 0.0)

        run = runner.run_suite("s1", agent, scorer)
        assert run.results[0].passed is True

    def test_run_suite_handles_errors(self) -> None:
        """Should handle agent errors gracefully."""
        runtime = EvalsRuntime()
        runner = runtime.get_runner("custom")

        cases = [EvalCase(id="c1", name="Error", input={"x": 1})]
        runner.create_suite(EvalSuite(id="s1", name="Error Test", cases=cases))

        def agent(input: dict) -> dict:
            raise ValueError("Agent error")

        run = runner.run_suite("s1", agent)
        assert run.results[0].passed is False
        assert "Agent error" in run.results[0].error

    def test_compute_metrics(self) -> None:
        """Should compute metrics from run."""
        runtime = EvalsRuntime()
        runner = runtime.get_runner("custom")

        cases = [
            EvalCase(id="c1", name="Pass", input={}, expected={}),
            EvalCase(id="c2", name="Fail", input={}, expected={"x": 1}),
        ]
        runner.create_suite(EvalSuite(id="s1", name="Test", cases=cases))

        def agent(input: dict) -> dict:
            return {}

        run = runner.run_suite("s1", agent)
        metrics = runner.compute_metrics(run)

        assert metrics.total_cases == 2
        assert metrics.passed == 1
        assert metrics.failed == 1
        assert metrics.pass_rate == 0.5

    def test_health_check(self) -> None:
        """Should return healthy status."""
        runtime = EvalsRuntime()
        runner = runtime.get_runner("custom")
        health = runner.health_check()
        assert health.healthy is True
        assert health.backend == "custom"
