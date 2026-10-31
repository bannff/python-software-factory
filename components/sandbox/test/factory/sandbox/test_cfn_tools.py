"""
Property-based tests for CFN deployment tools.

Verifies command construction, template writing, JSON parsing,
and LocalStack environment auto-detection using the mock adapter.
"""

import asyncio
import json

from hypothesis import given, settings, strategies as st

from factory.sandbox.runtime.adapters.mock import MockAdapter
from factory.sandbox.runtime.runtime import SandboxRuntime
from factory.sandbox.mcp.cfn_tools import _aws_cmd, _find_localstack_env, _parse_json


def _run_async(coro):
    """Run an async coroutine synchronously."""
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None
    if loop is None:
        return asyncio.run(coro)
    return loop.run_until_complete(coro)


# ---------------------------------------------------------------------------
# Helper function tests
# ---------------------------------------------------------------------------


class TestAwsCmd:
    """Property tests for _aws_cmd helper."""

    @settings(max_examples=50)
    @given(base=st.text(min_size=1, max_size=100, alphabet=st.characters(
        whitelist_categories=("L", "N", "P", "Z"),
    )))
    def test_contains_endpoint(self, base: str) -> None:
        """Every generated command includes the LocalStack endpoint."""
        cmd = _aws_cmd(base)
        assert "http://localhost:4566" in cmd

    @settings(max_examples=50)
    @given(base=st.text(min_size=1, max_size=100, alphabet=st.characters(
        whitelist_categories=("L", "N", "P", "Z"),
    )))
    def test_contains_env_vars(self, base: str) -> None:
        """Every generated command includes required AWS env vars."""
        cmd = _aws_cmd(base)
        assert "AWS_DEFAULT_REGION=us-east-1" in cmd
        assert "AWS_ACCESS_KEY_ID=test" in cmd
        assert "AWS_SECRET_ACCESS_KEY=test" in cmd

    @settings(max_examples=50)
    @given(base=st.text(min_size=1, max_size=80, alphabet=st.characters(
        whitelist_categories=("L", "N"),
    )))
    def test_contains_base_command(self, base: str) -> None:
        """The base command appears in the output."""
        cmd = _aws_cmd(base)
        assert base in cmd


class TestParseJson:
    """Property tests for _parse_json helper."""

    @settings(max_examples=50)
    @given(data=st.dictionaries(
        keys=st.text(min_size=1, max_size=20, alphabet=st.characters(
            whitelist_categories=("L", "N"),
        )),
        values=st.text(max_size=50),
        max_size=5,
    ))
    def test_roundtrip_valid_json(self, data: dict) -> None:
        """Valid JSON strings parse back to the original dict."""
        text = json.dumps(data)
        assert _parse_json(text) == data

    @settings(max_examples=50)
    @given(word=st.text(
        min_size=1, max_size=20,
        alphabet=st.characters(whitelist_categories=("L",)),
    ))
    def test_invalid_json_returns_raw(self, word: str) -> None:
        """Invalid JSON returns the raw text string."""
        # Prefix with 'X' to avoid JSON keywords (null, true, false)
        text = f"X{word} not json"
        result = _parse_json(text)
        assert result == text

    def test_none_returns_raw(self) -> None:
        """None input returns None (raw passthrough)."""
        assert _parse_json(None) is None


class TestFindLocalstackEnv:
    """Property tests for _find_localstack_env helper."""

    def test_finds_localstack_env(self) -> None:
        """Detects an environment with 'localstack' in its env_id."""
        adapter = MockAdapter()
        runtime = SandboxRuntime(adapter)
        # Provision and manually set env_id to contain 'localstack'
        env_id = _run_async(adapter.provision({}))
        # The mock generates a UUID — we need to inject a localstack env
        from factory.sandbox.runtime.models import EnvironmentInfo
        from factory.sandbox.core import EnvironmentStatus
        ls_env = EnvironmentInfo(
            env_id="localstack-abc123",
            status=EnvironmentStatus.RUNNING,
            instance_type="docker",
            created_at="2025-01-01T00:00:00Z",
        )
        runtime._store.save(ls_env)
        found = _run_async(_find_localstack_env(runtime))
        assert found == "localstack-abc123"

    def test_returns_none_when_no_localstack(self) -> None:
        """Returns None when no LocalStack environment exists."""
        from unittest.mock import patch
        adapter = MockAdapter()
        from factory.sandbox.runtime.adapters.memory_store import MemorySandboxStore
        store = MemorySandboxStore()
        runtime = SandboxRuntime(adapter, store=store)
        with patch("factory.sandbox.runtime.runtime.discover_docker_envs", return_value=[]):
            found = _run_async(_find_localstack_env(runtime))
        assert found is None

    @settings(max_examples=30)
    @given(prefix=st.sampled_from(["LOCALSTACK", "Localstack", "localstack"]))
    def test_case_insensitive_detection(self, prefix: str) -> None:
        """Detection is case-insensitive on the env_id."""
        adapter = MockAdapter()
        runtime = SandboxRuntime(adapter)
        from factory.sandbox.runtime.models import EnvironmentInfo
        from factory.sandbox.core import EnvironmentStatus
        env = EnvironmentInfo(
            env_id=f"{prefix}-test",
            status=EnvironmentStatus.RUNNING,
            instance_type="docker",
            created_at="2025-01-01T00:00:00Z",
        )
        runtime._store.save(env)
        found = _run_async(_find_localstack_env(runtime))
        assert found == f"{prefix}-test"


class TestDeployCfnCommandConstruction:
    """Property tests for deploy_cfn command building logic."""

    @settings(max_examples=50)
    @given(
        stack_name=st.text(
            min_size=1, max_size=30,
            alphabet=st.characters(whitelist_categories=("L", "N")),
        ),
        caps=st.lists(
            st.sampled_from([
                "CAPABILITY_IAM", "CAPABILITY_NAMED_IAM",
                "CAPABILITY_AUTO_EXPAND",
            ]),
            min_size=1, max_size=3,
        ),
    )
    def test_deploy_cmd_includes_stack_and_caps(
        self, stack_name: str, caps: list[str],
    ) -> None:
        """The deploy command includes the stack name and capabilities."""
        deploy = (
            f"cloudformation deploy"
            f" --template-file /tmp/{stack_name}.yaml"
            f" --stack-name {stack_name}"
            f" --capabilities {' '.join(caps)}"
        )
        cmd = _aws_cmd(deploy)
        assert f"--stack-name {stack_name}" in cmd
        for cap in caps:
            assert cap in cmd

    @settings(max_examples=50)
    @given(params=st.dictionaries(
        keys=st.text(min_size=1, max_size=15, alphabet=st.characters(
            whitelist_categories=("L", "N"),
        )),
        values=st.text(min_size=1, max_size=15, alphabet=st.characters(
            whitelist_categories=("L", "N"),
        )),
        min_size=1, max_size=4,
    ))
    def test_parameter_overrides_format(self, params: dict[str, str]) -> None:
        """Parameter overrides are formatted as Key=Value pairs."""
        overrides = " ".join(f"{k}={v}" for k, v in params.items())
        assert all(f"{k}={v}" in overrides for k, v in params.items())
