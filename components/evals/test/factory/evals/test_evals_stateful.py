"""Stateful property tests for CustomEvalRunner (Hypothesis).

Properties: suite CRUD consistency, run lifecycle invariants,
metrics arithmetic (passed+failed==total, pass_rate in [0,1]).
"""
from hypothesis import given, settings, strategies as st
from hypothesis.stateful import RuleBasedStateMachine, rule, initialize, invariant

from factory.evals.runtime.adapters.custom_adapter import CustomEvalRunner
from factory.evals.runtime.ports import EvalCase, EvalSuite, EvalRun, EvalResult

safe_id = st.text(
    min_size=1, max_size=20,
    alphabet=st.characters(whitelist_categories=("L", "N")),
)
safe_text = st.text(min_size=0, max_size=100)


def _echo_agent(inp: dict) -> dict:
    return inp


class EvalRunnerStateMachine(RuleBasedStateMachine):
    """Stateful test for CustomEvalRunner."""

    def __init__(self):
        super().__init__()
        self.runner: CustomEvalRunner | None = None
        self.suite_ids: set[str] = set()
        self.run_ids: dict[str, str] = {}  # run_id -> suite_id

    @initialize()
    def init_runner(self):
        self.runner = CustomEvalRunner()
        self.suite_ids = set()
        self.run_ids = {}

    @rule(sid=safe_id, name=safe_text)
    def create_suite(self, sid: str, name: str):
        """Create a suite and track it."""
        cases = [EvalCase(id=f"{sid}_c1", name="c", input={"x": 1}, expected={"x": 1})]
        suite = EvalSuite(id=sid, name=name, cases=cases)
        result = self.runner.create_suite(suite)
        assert result.id == sid
        self.suite_ids.add(sid)

    @rule(sid=safe_id)
    def get_suite(self, sid: str):
        """Get suite — found if created, None otherwise."""
        result = self.runner.get_suite(sid)
        if sid in self.suite_ids:
            assert result is not None, f"Suite {sid} should exist"
            assert result.id == sid
        else:
            assert result is None, f"Suite {sid} should not exist"

    @rule()
    def run_random_suite(self):
        """Run a suite if any exist, creating a tracked run."""
        if not self.suite_ids:
            return
        sid = next(iter(self.suite_ids))
        run = self.runner.run_suite(sid, _echo_agent)
        assert run.status == "completed"
        self.run_ids[run.id] = sid

    @rule(rid=safe_id)
    def get_run(self, rid: str):
        """Get run — found if executed, None otherwise."""
        result = self.runner.get_run(rid)
        if rid in self.run_ids:
            assert result is not None
            assert result.id == rid
        else:
            assert result is None

    @rule()
    def list_runs_unfiltered(self):
        """List all runs matches tracked count."""
        runs = self.runner.list_runs()
        assert len(runs) == len(self.run_ids)

    @rule()
    def list_runs_filtered(self):
        """Filtered list only returns runs for that suite."""
        if not self.suite_ids:
            return
        sid = next(iter(self.suite_ids))
        runs = self.runner.list_runs(suite_id=sid)
        expected = sum(1 for s in self.run_ids.values() if s == sid)
        assert len(runs) == expected

    @invariant()
    def suite_count_matches(self):
        """list_suites count == number of unique created suites."""
        if self.runner is None:
            return
        assert len(self.runner.list_suites()) == len(self.suite_ids)

    @invariant()
    def all_runs_completed(self):
        """Every stored run has status 'completed'."""
        if self.runner is None:
            return
        for rid in self.run_ids:
            run = self.runner.get_run(rid)
            assert run.status == "completed"

    @invariant()
    def metrics_consistent(self):
        """passed + failed == total_cases and pass_rate in [0,1]."""
        if self.runner is None:
            return
        for rid in self.run_ids:
            run = self.runner.get_run(rid)
            m = self.runner.compute_metrics(run)
            assert m.passed + m.failed == m.total_cases
            assert 0.0 <= m.pass_rate <= 1.0
            assert m.total_cases == len(run.results)


TestEvalRunnerStateful = EvalRunnerStateMachine.TestCase
TestEvalRunnerStateful.settings = settings(max_examples=50, stateful_step_count=20)


@given(name=safe_text, desc=safe_text)
@settings(max_examples=50)
def test_suite_roundtrip_with_arbitrary_names(name: str, desc: str):
    """Suite creation with arbitrary names/descriptions roundtrips."""
    runner = CustomEvalRunner()
    suite = EvalSuite(id="s1", name=name, description=desc, cases=[])
    runner.create_suite(suite)
    got = runner.get_suite("s1")
    assert got.name == name
    assert got.description == desc


@given(n=st.integers(min_value=0, max_value=20))
@settings(max_examples=50)
def test_metrics_on_variable_case_counts(n: int):
    """Metrics are correct for suites with 0..N cases."""
    runner = CustomEvalRunner()
    cases = [EvalCase(id=f"c{i}", name=f"c{i}", input={}, expected={}) for i in range(n)]
    runner.create_suite(EvalSuite(id="s1", name="t", cases=cases))
    run = runner.run_suite("s1", _echo_agent)
    m = runner.compute_metrics(run)
    assert m.total_cases == n
    assert m.passed + m.failed == n
    if n > 0:
        assert 0.0 <= m.pass_rate <= 1.0
        assert m.avg_duration_ms >= 0.0


@given(
    results=st.lists(
        st.booleans(),
        min_size=1,
        max_size=30,
    )
)
@settings(max_examples=50)
def test_metrics_pass_rate_matches_results(results: list[bool]):
    """pass_rate == passed / total for arbitrary pass/fail combos."""
    runner = CustomEvalRunner()
    run = EvalRun(id="r1", suite_id="s1", status="completed")
    for i, passed in enumerate(results):
        run.results.append(EvalResult(
            case_id=f"c{i}", passed=passed,
            score=1.0 if passed else 0.0, duration_ms=1.0,
        ))
    m = runner.compute_metrics(run)
    expected_rate = sum(results) / len(results)
    assert abs(m.pass_rate - expected_rate) < 1e-9


@settings(max_examples=50)
@given(data=st.dictionaries(st.text(max_size=10), st.integers()))
def test_eval_case_with_arbitrary_input(data: dict):
    """EvalCase accepts arbitrary input dicts without error."""
    runner = CustomEvalRunner()
    case = EvalCase(id="c1", name="fuzz", input=data, expected=data)
    suite = EvalSuite(id="s1", name="fuzz", cases=[case])
    runner.create_suite(suite)
    run = runner.run_suite("s1", _echo_agent)
    assert run.results[0].passed is True
