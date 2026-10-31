"""
Property-based tests for MockAdapter sandbox lifecycle.

Uses Hypothesis to verify that the MockAdapter maintains correct state
across arbitrary sequences of provision, execute, upload, download,
and terminate operations.
"""

import asyncio

from hypothesis import given, settings, strategies as st
from hypothesis.stateful import RuleBasedStateMachine, rule, initialize, invariant

from factory.sandbox.runtime.adapters.mock import MockAdapter


def _run_async(coro):
    """Run an async coroutine synchronously."""
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None
    if loop is None:
        return asyncio.run(coro)
    else:
        return loop.run_until_complete(coro)


# ---------------------------------------------------------------------------
# Property tests (stateless)
# ---------------------------------------------------------------------------


class TestProvisionProperties:
    """Property tests for provisioning."""

    @settings(max_examples=50)
    @given(n=st.integers(min_value=2, max_value=8))
    def test_provision_returns_unique_ids(self, n: int) -> None:
        """Multiple provisions always return distinct env_ids."""
        adapter = MockAdapter()
        ids = [_run_async(adapter.provision({"i": i})) for i in range(n)]
        assert len(set(ids)) == n

    @settings(max_examples=50)
    @given(config=st.fixed_dictionaries({"type": st.text(min_size=1, max_size=20)}))
    def test_provision_then_status_running(self, config: dict) -> None:
        """After provision, get_status returns 'running'."""
        adapter = MockAdapter()
        env_id = _run_async(adapter.provision(config))
        status = _run_async(adapter.get_status(env_id))
        assert status["status"] == "running"


class TestTerminateProperties:
    """Property tests for termination."""

    @settings(max_examples=50)
    @given(config=st.fixed_dictionaries({"x": st.integers()}))
    def test_terminate_then_status_terminated(self, config: dict) -> None:
        """After terminate, get_status returns 'terminated'."""
        adapter = MockAdapter()
        env_id = _run_async(adapter.provision(config))
        _run_async(adapter.terminate(env_id))
        status = _run_async(adapter.get_status(env_id))
        assert status["status"] == "terminated"

    @settings(max_examples=50)
    @given(env_id=st.uuids().map(str))
    def test_unknown_env_status(self, env_id: str) -> None:
        """get_status on a non-existent env returns 'unknown'."""
        adapter = MockAdapter()
        status = _run_async(adapter.get_status(env_id))
        assert status["status"] == "unknown"


class TestExecuteProperties:
    """Property tests for command execution."""

    @settings(max_examples=50)
    @given(command=st.text(min_size=1, max_size=100))
    def test_execute_on_valid_env_succeeds(self, command: str) -> None:
        """Execute on a provisioned env returns exit_code=0."""
        adapter = MockAdapter()
        env_id = _run_async(adapter.provision({}))
        result = _run_async(adapter.execute(env_id, command))
        assert result["exit_code"] == 0
        assert result["stdout"] != ""

    @settings(max_examples=50)
    @given(env_id=st.uuids().map(str), command=st.text(min_size=1, max_size=50))
    def test_execute_on_invalid_env_fails(self, env_id: str, command: str) -> None:
        """Execute on a non-existent env returns exit_code=1."""
        adapter = MockAdapter()
        result = _run_async(adapter.execute(env_id, command))
        assert result["exit_code"] == 1


class TestFileProperties:
    """Property tests for file operations."""

    @settings(max_examples=50)
    @given(
        local=st.text(min_size=1, max_size=50, alphabet=st.characters(categories=("L", "N", "P"))),
        remote=st.text(min_size=1, max_size=50, alphabet=st.characters(categories=("L", "N", "P"))),
    )
    def test_upload_on_valid_env_succeeds(self, local: str, remote: str) -> None:
        """Upload on a provisioned env returns success=True."""
        adapter = MockAdapter()
        env_id = _run_async(adapter.provision({}))
        result = _run_async(adapter.upload_file(env_id, local, remote))
        assert result["success"] is True

    @settings(max_examples=50)
    @given(env_id=st.uuids().map(str))
    def test_upload_on_invalid_env_fails(self, env_id: str) -> None:
        """Upload on a non-existent env returns success=False."""
        adapter = MockAdapter()
        result = _run_async(adapter.upload_file(env_id, "/a", "/b"))
        assert result["success"] is False


class TestHealthCheckProperties:
    """Property tests for health_check."""

    @settings(max_examples=50)
    @given(n=st.integers(min_value=0, max_value=10))
    def test_health_check_counts_environments(self, n: int) -> None:
        """health_check environments count matches provisioned count."""
        adapter = MockAdapter()
        for _ in range(n):
            _run_async(adapter.provision({}))
        health = adapter.health_check()
        assert health["healthy"] is True
        assert health["adapter"] == "mock"
        assert health["environments"] == n


# ---------------------------------------------------------------------------
# Stateful lifecycle test
# ---------------------------------------------------------------------------


class MockAdapterStateMachine(RuleBasedStateMachine):
    """Stateful test: provision, execute, terminate in arbitrary order."""

    def __init__(self):
        super().__init__()
        self.adapter = None
        self.env_states: dict[str, str] = {}  # env_id -> expected status

    def _run(self, coro):
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None
        if loop is None:
            return asyncio.run(coro)
        return loop.run_until_complete(coro)

    @initialize()
    def init_adapter(self):
        self.adapter = MockAdapter()
        self.env_states = {}

    @rule(config=st.fixed_dictionaries({"t": st.text(max_size=10)}))
    def provision_env(self, config: dict):
        env_id = self._run(self.adapter.provision(config))
        self.env_states[env_id] = "running"

    @rule(command=st.text(min_size=1, max_size=30))
    def execute_on_random_env(self, command: str):
        running = [e for e, s in self.env_states.items() if s == "running"]
        if running:
            result = self._run(self.adapter.execute(running[0], command))
            assert result["exit_code"] == 0

    @rule()
    def terminate_random_env(self):
        running = [e for e, s in self.env_states.items() if s == "running"]
        if running:
            self._run(self.adapter.terminate(running[0]))
            self.env_states[running[0]] = "terminated"

    @invariant()
    def health_count_matches(self):
        if self.adapter is not None:
            health = self.adapter.health_check()
            assert health["environments"] == len(self.env_states)

    @invariant()
    def all_statuses_correct(self):
        if self.adapter is not None:
            for env_id, expected in self.env_states.items():
                status = self._run(self.adapter.get_status(env_id))
                assert status["status"] == expected


TestMockAdapterStateful = MockAdapterStateMachine.TestCase
TestMockAdapterStateful.settings = settings(max_examples=50, stateful_step_count=15)
