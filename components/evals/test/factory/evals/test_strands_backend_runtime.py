"""Runtime backend selection: strands is a known backend; custom stays SDK-free."""
from __future__ import annotations

import sys

import pytest

from factory.evals.runtime.runtime import EvalsRuntime
from factory.mcp_utils.runtime.tool_failure import SafeDiagnostic


def test_available_backends_includes_strands_and_custom():
    assert set(EvalsRuntime.available_backends()) == {"custom", "strands"}


def test_strands_runner_is_the_strands_adapter():
    from factory.evals.runtime.adapters.strands_adapter import StrandsEvalRunner
    runtime = EvalsRuntime()
    runner = runtime.get_runner("strands")
    assert isinstance(runner, StrandsEvalRunner)


def test_selecting_custom_never_imports_the_sdk():
    """Slim deployments composing only the custom path must not pull strands_evals."""
    sys.modules.pop("strands_evals", None)
    runtime = EvalsRuntime()
    runtime.get_runner("custom")
    assert "strands_evals" not in sys.modules


def test_unknown_backend_is_fail_closed():
    runtime = EvalsRuntime()
    with pytest.raises(SafeDiagnostic):
        runtime.get_runner("bogus")


def test_health_check_reports_strands_availability():
    runtime = EvalsRuntime()
    runtime.get_runner("strands")
    health = runtime.health_check()
    strands_health = [value for key, value in health.items() if key.startswith("strands:")]
    assert strands_health and strands_health[0].backend == "strands"
