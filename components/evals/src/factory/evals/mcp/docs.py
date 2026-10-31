"""Documentation content for evals MCP resources."""

EVALS_DOCS = {
    "overview": {
        "title": "Evals Brick Overview",
        "content": """# Evals Brick

Agent benchmarking and evaluation framework for the Python Factory.

## Core Concepts

- **EvalSuite**: Collection of test cases for benchmarking
- **EvalCase**: Single test with input, expected output, and metadata
- **EvalRun**: Execution of a suite against an agent
- **EvalResult**: Outcome of a single case evaluation
- **EvalMetrics**: Aggregated statistics from a run

## Durable Terminal Records

`evals_record_run` is the sole terminal-record writer. It creates an immutable,
JSON-safe document in the Storage brick with a schema version, record kind,
terminal state, and deterministic SHA-256 content hash. An equal retry returns
`matched`; a divergent write returns `conflict` without replacing the original.

Full evaluation runs use `eval-{run_id}`. P/R/F1 score projections use the
isolated `eval-score-{run_id}` identity, so they cannot overwrite run artifacts.
After a successful Storage commit, lifecycle events and Graph receive only an
immutable pointer and scalar summary; neither owns the evidence payload.

## Quick Start

1. Create a suite:
```
evals_create_suite(
    suite_id="my-suite",
    name="My Evaluation Suite",
    cases=[{"id": "case-1", "name": "Test 1", "input": {"query": "hello"}}]
)
```

2. List suites:
```
evals_list_suites()
```

3. Record a completed run through the canonical writer:
```
evals_record_run(run_id="run-123", experiment_name="my-suite", verdict="PASS",
                 pass_rate=1.0, avg_score=1.0, total_cases=1, passed=1)
```

## Evaluation Path

The production evaluator path is framework-neutral. `evals_evaluate` and
`evals_evaluate_multi` score normalized evidence through the local evaluator
registry; computational evaluators remain deterministic array-based functions.

## Adapters

- `custom` - Framework-neutral in-memory evaluation runner (default and production path)

## MCP Tools

- `evals_create_suite` - Create evaluation suite
- `evals_get_suite` - Get suite by ID
- `evals_list_suites` - List all suites
- `evals_get_run` - Get suite-run state
- `evals_list_runs` - List suite-run state
- `evals_record_run` - Create or match one immutable terminal record
- `evals_run_simulation` - Run a multi-turn ActorSimulator evaluation
- `evals_run_tool_chaos` - Run paired native ToolSimulator fault evaluation
""",
    },
    "adapters": {
        "title": "Adapter Documentation",
        "content": """# Evals Adapters

The evals brick uses a polymorphic adapter pattern for different backends.

## Custom Adapter

The framework-neutral in-memory evaluation runner is the sole backend.

```python
runtime = EvalsRuntime()
runner = runtime.get_runner("custom")
```

Features:
- No agent-framework dependency
- Deterministic custom scorer support
- Suitable for production policy evaluators and tests

## Creating Custom Adapters

Implement the `EvalRunner` protocol:

```python
class MyAdapter:
    def create_suite(self, suite: EvalSuite) -> EvalSuite: ...
    def get_suite(self, suite_id: str) -> EvalSuite | None: ...
    def list_suites(self) -> list[EvalSuite]: ...
    def run_suite(self, suite_id, agent_fn, scorer_fn) -> EvalRun: ...
    def get_run(self, run_id: str) -> EvalRun | None: ...
    def list_runs(self, suite_id: str | None) -> list[EvalRun]: ...
    def compute_metrics(self, run: EvalRun) -> EvalMetrics: ...
    def health_check(self) -> EvalHealth: ...
```
""",
    },
    "metrics": {
        "title": "Metrics Documentation",
        "content": """# Evaluation Metrics

Metrics computed from evaluation runs.

## Standard Metrics

| Metric | Description |
|--------|-------------|
| total_cases | Number of test cases |
| passed | Cases that passed |
| failed | Cases that failed |
| pass_rate | Percentage passed (0.0-1.0) |
| avg_score | Average score across cases |
| avg_duration_ms | Average execution time |

## Custom Metrics

Add custom metrics via scorer functions:

```python
def my_scorer(case: EvalCase, actual: dict) -> EvalResult:
    return EvalResult(
        case_id=case.id,
        passed=actual == case.expected,
        score=compute_similarity(actual, case.expected),
        metrics={"latency": 100, "tokens": 50}
    )
```

## Aggregation

Metrics are aggregated per run:

```python
metrics = runner.compute_metrics(run)
print(f"Pass rate: {metrics.pass_rate:.2%}")
print(f"Custom: {metrics.custom_metrics}")
```
""",
    },
}
