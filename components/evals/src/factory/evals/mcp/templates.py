"""Prompt templates for evals MCP prompts."""

PROMPT_TEMPLATES = {
    "create_eval": {
        "description": "Guide for creating an evaluation suite",
        "template": """# Create Evaluation: {name}

## Purpose
{purpose}

## Suite Definition

```python
evals_create_suite(
    suite_id="{suite_id}",
    name="{name}",
    description="{purpose}",
    cases=[
        {{
            "id": "case-1",
            "name": "Test case 1",
            "input": {{"query": "example input"}},
            "expected": {{"response": "expected output"}}
        }}
    ]
)
```

## Test Case Structure

| Field | Required | Description |
|-------|----------|-------------|
| id | Yes | Unique case identifier |
| name | Yes | Human-readable name |
| input | Yes | Input data for agent |
| expected | No | Expected output for scoring |
| metadata | No | Additional context |

## Verification

```
evals_get_suite(suite_id="{suite_id}")
```
""",
    },
    "run_eval": {
        "description": "Guide for running evaluations",
        "template": """# Run Evaluation: {suite_id}

## Prerequisites
- Suite exists: `evals_get_suite(suite_id="{suite_id}")`
- Agent function defined

## Running via API

```python
from factory.evals.runtime.runtime import get_runtime

runtime = get_runtime()
runner = runtime.get_runner("{backend}")

def my_agent(input_data: dict) -> dict:
    # Your agent logic here
    return {{"response": "..."}}

run = runner.run_suite("{suite_id}", my_agent)
print(f"Run ID: {{run.id}}")
```

## Check Results

```
evals_get_run(run_id="<run_id>")
evals_list_runs(suite_id="{suite_id}")
```

## Compute Metrics

```python
metrics = runner.compute_metrics(run)
print(f"Pass rate: {{metrics.pass_rate:.2%}}")
```
""",
    },
    "analyze_results": {
        "description": "Guide for analyzing evaluation results",
        "template": """# Analyze Results: {run_id}

## Get Run Details

```
evals_get_run(run_id="{run_id}")
```

## Key Metrics to Review

1. **Pass Rate**: Overall success percentage
2. **Average Score**: Quality metric across cases
3. **Duration**: Performance characteristics
4. **Failed Cases**: Identify problem areas

## Analysis Steps

### 1. Get Run Summary
```python
run = runner.get_run("{run_id}")
print(f"Status: {{run.status}}")
print(f"Results: {{len(run.results)}}")
```

### 2. Compute Metrics
```python
metrics = runner.compute_metrics(run)
print(f"Pass rate: {{metrics.pass_rate:.2%}}")
print(f"Avg score: {{metrics.avg_score:.2f}}")
```

### 3. Review Failures
```python
failures = [r for r in run.results if not r.passed]
for f in failures:
    print(f"Case {{f.case_id}}: {{f.error}}")
```

## Common Issues

| Symptom | Possible Cause | Action |
|---------|---------------|--------|
| Low pass rate | Bad test cases | Review expected values |
| High latency | Agent bottleneck | Profile agent code |
| Errors | Input format | Check case inputs |
""",
    },
    "compare_runs": {
        "description": "Guide for comparing evaluation runs",
        "template": """# Compare Runs

## Runs to Compare
- Run A: {run_a}
- Run B: {run_b}

## Get Both Runs

```
evals_get_run(run_id="{run_a}")
evals_get_run(run_id="{run_b}")
```

## Comparison Steps

### 1. Load Runs
```python
run_a = runner.get_run("{run_a}")
run_b = runner.get_run("{run_b}")
```

### 2. Compare Metrics
```python
metrics_a = runner.compute_metrics(run_a)
metrics_b = runner.compute_metrics(run_b)

print(f"Pass rate: {{metrics_a.pass_rate:.2%}} vs {{metrics_b.pass_rate:.2%}}")
print(f"Avg score: {{metrics_a.avg_score:.2f}} vs {{metrics_b.avg_score:.2f}}")
print(f"Avg time: {{metrics_a.avg_duration_ms:.0f}}ms vs {{metrics_b.avg_duration_ms:.0f}}ms")
```

### 3. Identify Regressions
```python
results_a = {{r.case_id: r for r in run_a.results}}
results_b = {{r.case_id: r for r in run_b.results}}

for case_id in results_a:
    if case_id in results_b:
        if results_a[case_id].passed and not results_b[case_id].passed:
            print(f"Regression: {{case_id}}")
```

## Metrics Summary

| Metric | Run A | Run B | Delta |
|--------|-------|-------|-------|
| Pass Rate | - | - | - |
| Avg Score | - | - | - |
| Avg Duration | - | - | - |
""",
    },
}
