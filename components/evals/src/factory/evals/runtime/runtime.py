"""Framework-neutral Evals runtime factory."""
from __future__ import annotations

from typing import Any

from factory.mcp_utils.runtime.tool_failure import SafeDiagnostic

from .ports import EvalHealth, EvalRunner, ExperimentConfig, ExperimentReport

_BACKENDS = ("custom", "strands")


class EvalsRuntime:
    """Compose the custom evaluator runtime and durable persistence port."""

    def __init__(self, config: dict[str, Any] | None = None) -> None:
        self._config = config or {}
        from .adapters.persistence import build_eval_persistence
        self._persistence = build_eval_persistence(self._config)
        self._runners: dict[str, EvalRunner] = {}

    def get_runner(self, backend: str = "custom", **kwargs: Any) -> EvalRunner:
        if backend not in _BACKENDS:
            raise SafeDiagnostic(
                f"Unknown evals backend: {backend}. Available: {self.available_backends()}"
            )
        key = f"{backend}:{hash(frozenset(kwargs.items()))}"
        if key not in self._runners:
            self._runners[key] = self._create_runner(backend, **kwargs)
        return self._runners[key]

    def _create_runner(self, backend: str, **kwargs: Any) -> EvalRunner:
        if backend == "strands":
            from .adapters.strands_adapter import StrandsEvalRunner
            return StrandsEvalRunner(persistence=self._persistence, **kwargs)
        from .adapters.custom_adapter import CustomEvalRunner
        return CustomEvalRunner(persistence=self._persistence, **kwargs)

    def _strands_runner(self) -> Any:
        return self.get_runner("strands")

    def run_experiment(self, config: ExperimentConfig) -> ExperimentReport:
        """Run a Strands experiment via the strands adapter."""
        return self._strands_runner().run_experiment(config)

    def generate_experiment(
        self, context: str, task_description: str,
        num_cases: int = 5, evaluator_name: str = "output",
    ) -> ExperimentConfig:
        """Generate an experiment config from context via the strands adapter."""
        return self._strands_runner().generate_experiment(
            context, task_description, num_cases, evaluator_name,
        )

    def run_simulation(
        self, config: ExperimentConfig, max_turns: int = 10,
    ) -> ExperimentReport:
        """Run a multi-turn ActorSimulator experiment via the strands adapter."""
        return self._strands_runner().run_simulation(config, max_turns)

    def save_experiment(self, config: ExperimentConfig, filename: str) -> dict:
        """Serialize an experiment config via the strands adapter."""
        return self._strands_runner().save_experiment(config, filename)

    def load_experiment(self, filename: str) -> ExperimentConfig:
        """Deserialize an experiment config via the strands adapter."""
        return self._strands_runner().load_experiment(filename)

    def list_saved_experiments(self) -> list[dict]:
        """List serialized experiment files via the strands adapter."""
        return self._strands_runner().list_saved_experiments()

    def list_evaluators(self) -> list[dict[str, Any]]:
        from .adapters.evaluator_catalog import get_available_evaluators
        return get_available_evaluators()

    def evaluate_with_real_session(
        self, input_text: str, output_text: str, evaluator_names: list[str],
        session_data: dict[str, Any] | None = None, rubric: str = "",
        expected_output: str | None = None,
        otel_spans_json: list[str] | None = None, session: Any | None = None,
        actual_interactions: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        from .adapters.session_evaluator import evaluate_with_real_session
        return evaluate_with_real_session(
            input_text, output_text, evaluator_names,
            session_data=session_data, rubric=rubric,
            expected_output=expected_output, otel_spans_json=otel_spans_json,
            session=session, actual_interactions=actual_interactions,
        )

    def evaluate_output(
        self, input_text: str, output_text: str,
        evaluator_name: str = "non_empty", rubric: str = "",
        expected_output: str | None = None, framework: str = "deterministic",
    ) -> dict[str, Any]:
        from .adapters.evaluator_adapter import evaluate_output
        return evaluate_output(
            input_text, output_text, evaluator_name, rubric,
            expected_output, framework,
        )

    def evaluate_output_multi(
        self, input_text: str, output_text: str,
        evaluator_names: list[str], rubric: str = "",
        expected_output: str | None = None, framework: str = "deterministic",
        actual_trajectory: list[Any] | None = None,
        expected_trajectory: list[Any] | None = None,
        options: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        from .adapters.evaluator_adapter import evaluate_output_multi
        return evaluate_output_multi(
            input_text, output_text, evaluator_names, rubric,
            expected_output, framework,
            actual_trajectory=actual_trajectory,
            expected_trajectory=expected_trajectory, options=options,
        )

    def create_sop_session(
        self, agent_description: str, agent_tools: list[str] | None = None,
        evaluation_goals: str = "",
    ) -> dict[str, Any]:
        from .adapters.sop_adapter import create_sop_session
        return create_sop_session(agent_description, agent_tools, evaluation_goals)

    def generate_sop_test_data(
        self, session_id: str, num_cases: int = 10,
        evaluator_name: str = "output",
    ) -> dict[str, Any]:
        from .adapters.sop_adapter import generate_sop_test_data
        return generate_sop_test_data(session_id, num_cases, evaluator_name)

    def run_sop_evaluation(self, session_id: str, **kwargs: Any) -> dict[str, Any]:
        from .adapters.sop_adapter import run_sop_evaluation
        return run_sop_evaluation(session_id, **kwargs)

    def generate_sop_report(self, session_id: str) -> dict[str, Any]:
        from .adapters.sop_adapter import generate_sop_report
        return generate_sop_report(session_id, self._persistence)

    def get_sop_session(self, session_id: str) -> dict[str, Any]:
        from .adapters.sop_adapter import get_sop_session
        return get_sop_session(session_id)

    def list_sop_sessions(self) -> list[dict[str, Any]]:
        from .adapters.sop_adapter import list_sop_sessions
        return list_sop_sessions()

    def health_check(self) -> dict[str, EvalHealth]:
        return {name: runner.health_check() for name, runner in self._runners.items()}

    @property
    def suites(self) -> dict[str, Any]:
        runner = self.get_runner()
        return {suite.id: suite for suite in runner.list_suites()}

    @staticmethod
    def available_backends() -> list[str]:
        return list(_BACKENDS)


_runtime: EvalsRuntime | None = None


def get_runtime() -> EvalsRuntime:
    global _runtime
    if _runtime is None:
        _runtime = EvalsRuntime()
    return _runtime


def reset_runtime() -> None:
    global _runtime
    _runtime = None
