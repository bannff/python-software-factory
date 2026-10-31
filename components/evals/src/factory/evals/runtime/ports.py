"""Abstract ports for evals brick.

Ports define what capabilities the evaluation framework needs.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Protocol, Callable


@dataclass
class EvalHealth:
    """Health status for an eval backend."""
    healthy: bool
    backend: str
    latency_ms: float = 0.0
    message: str = ""


@dataclass
class EvalCase:
    """A single evaluation test case."""
    id: str
    name: str
    input: dict[str, Any] | str
    expected: dict[str, Any] | None = None
    expected_trajectory: list[str] | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    session_id: str = ""


@dataclass
class EvalResult:
    """Result from a single evaluation."""
    case_id: str
    passed: bool
    score: float = 0.0
    actual: dict[str, Any] = field(default_factory=dict)
    metrics: dict[str, float] = field(default_factory=dict)
    error: str | None = None
    reason: str = ""
    duration_ms: float = 0.0


@dataclass
class EvalSuite:
    """A collection of evaluation cases."""
    id: str
    name: str
    description: str = ""
    cases: list[EvalCase] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class EvalRun:
    """A complete evaluation run."""
    id: str
    suite_id: str
    started_at: datetime = field(default_factory=datetime.now)
    completed_at: datetime | None = None
    results: list[EvalResult] = field(default_factory=list)
    summary: dict[str, Any] = field(default_factory=dict)
    status: str = "pending"  # pending, running, completed, failed


@dataclass
class EvalMetrics:
    """Aggregated metrics from an evaluation run."""
    total_cases: int = 0
    passed: int = 0
    failed: int = 0
    pass_rate: float = 0.0
    avg_score: float = 0.0
    avg_duration_ms: float = 0.0
    custom_metrics: dict[str, float] = field(default_factory=dict)


@dataclass
class EvalAgentConfig:
    """Declarative agent configuration for running evals."""
    model_id: str = "us.anthropic.claude-sonnet-4-5-20250929-v1:0"
    system_prompt: str = "You are a helpful assistant."
    temperature: float = 0.1
    max_tokens: int = 4096
    tools: list[str] = field(default_factory=list)
    provider: str = "bedrock"
    agent_id: str | None = None


@dataclass
class ExperimentConfig:
    """Framework-neutral evaluation experiment configuration."""
    cases: list[EvalCase] = field(default_factory=list)
    evaluator_names: list[str] = field(default_factory=list)
    agent_config: EvalAgentConfig | None = None
    rubric: str = ""
    name: str = ""
    run_id: str = ""


@dataclass
class ExperimentReport:
    """Results from a framework-neutral evaluation run."""
    experiment_name: str = ""
    case_results: list[dict[str, Any]] = field(default_factory=list)
    summary: dict[str, Any] = field(default_factory=dict)
    evaluator_names: list[str] = field(default_factory=list)


class NeutralEvaluator(Protocol):
    """Port: A single framework-neutral evaluator over neutral evidence."""

    name: str

    def evaluate(self, data: Any) -> list[Any]:
        """Score neutral ``EvaluationData`` into neutral ``EvaluationOutput`` rows."""
        ...


class EvaluatorProviderPort(Protocol):
    """Port: A judging framework selected by name on the evaluator rail."""

    framework: str

    def available(self) -> list[str]:
        """Return the evaluator alias names this provider can build."""
        ...

    def build(
        self, names: list[str], rubric: str = "",
        options: dict[str, Any] | None = None,
    ) -> list[NeutralEvaluator]:
        """Build neutral evaluators for ``names`` (raise ValueError on unknown)."""
        ...


class EvalPersistencePort(Protocol):
    """Port: Durable persistence for evaluation suites and runs."""

    def persist_suite(self, suite: EvalSuite) -> None:
        """Persist an evaluation suite."""
        ...

    def persist_run(self, run: EvalRun, metrics: EvalMetrics) -> None:
        """Persist a completed evaluation run and its metrics."""
        ...


class EvalRunner(Protocol):
    """Port: Evaluation runner for benchmarking agents."""

    def create_suite(self, suite: EvalSuite) -> EvalSuite:
        """Create an evaluation suite."""
        ...

    def get_suite(self, suite_id: str) -> EvalSuite | None:
        """Get an evaluation suite by ID."""
        ...

    def list_suites(self) -> list[EvalSuite]:
        """List all evaluation suites."""
        ...

    def run_suite(
        self,
        suite_id: str,
        agent_fn: Callable[[dict[str, Any]], dict[str, Any]],
        scorer_fn: Callable[[EvalCase, dict[str, Any]], EvalResult] | None = None,
    ) -> EvalRun:
        """Run an evaluation suite against an agent."""
        ...

    def get_run(self, run_id: str) -> EvalRun | None:
        """Get an evaluation run by ID."""
        ...

    def list_runs(self, suite_id: str | None = None) -> list[EvalRun]:
        """List evaluation runs, optionally filtered by suite."""
        ...

    def compute_metrics(self, run: EvalRun) -> EvalMetrics:
        """Compute aggregated metrics from a run."""
        ...

    def health_check(self) -> EvalHealth:
        """Check runner health."""
        ...
