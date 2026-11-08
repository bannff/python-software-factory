"""Terminated envs refuse work, mock diff never invents files, and mock is machine-readable (#385)."""
from __future__ import annotations

import asyncio

from factory.sandbox.interface import Runtime
from factory.sandbox.mcp.dashboard_summary import build_dashboard_summary
from factory.sandbox.runtime.adapters.mock import MockAdapter
from factory.sandbox.runtime.profiles import list_profiles
from factory.sandbox.server import create_tool_catalog


def _setup():
    runtime = Runtime(MockAdapter())
    tools = {t.name: t.fn for t in asyncio.run(create_tool_catalog(runtime).list_tools())}
    env_id = asyncio.run(tools["sandbox.provision"]()).data.environment.env_id
    return runtime, tools, env_id


def test_terminated_env_refuses_execute_write_and_diff() -> None:
    _, tools, env_id = _setup()
    assert asyncio.run(tools["sandbox.terminate"](env_id=env_id)).ok
    calls = (
        tools["sandbox.execute"](env_id=env_id, command="echo nope"),
        tools["sandbox.write_file"](env_id=env_id, remote_path="/tmp/x", content="x"),
        tools["sandbox.diff"](env_id=env_id),
    )
    for call in calls:
        assert asyncio.run(call).error == "environment_terminated"


def test_unknown_env_is_typed_for_execute() -> None:
    _, tools, _ = _setup()
    assert asyncio.run(tools["sandbox.execute"](env_id="env-nope", command="ls")).error == "env_not_found"


def test_mock_diff_reports_not_a_repo_instead_of_garbage_paths() -> None:
    _, tools, env_id = _setup()
    result = asyncio.run(tools["sandbox.diff"](env_id=env_id)).data
    assert result.is_git_repo is False and result.files == []


def test_dashboard_profile_count_matches_list_profiles() -> None:
    runtime, _, _ = _setup()
    assert build_dashboard_summary(runtime)["overview"]["profiles"] == len(list_profiles())


def test_health_and_capabilities_say_simulated() -> None:
    runtime, tools, _ = _setup()
    assert runtime.health_check()["adapter"]["simulated"] is True
    caps = tools["sandbox.get_capabilities"]().data
    assert caps.simulated is True and "docker" in caps.adapters
