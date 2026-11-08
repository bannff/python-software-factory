"""Opt-in live smoke: a real container goes provision -> execute -> terminate (#385).

Runs only when a Docker daemon answers and the smoke image exists locally
(default ``alpine:latest``; override with SANDBOX_SMOKE_IMAGE). Never pulls.
"""
from __future__ import annotations

import asyncio
import os
import subprocess

import pytest

from factory.sandbox.interface import Runtime
from factory.sandbox.runtime.adapters.docker_adapter import DockerAdapter
from factory.sandbox.server import create_tool_catalog

IMAGE = os.environ.get("SANDBOX_SMOKE_IMAGE", "alpine:latest")


def _docker(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["docker", *args], capture_output=True, text=True, timeout=30, check=False)


def _available() -> bool:
    try:
        return _docker("info").returncode == 0 and _docker("image", "inspect", IMAGE).returncode == 0
    except (OSError, subprocess.TimeoutExpired):
        return False


pytestmark = pytest.mark.skipif(not _available(), reason=f"needs a Docker daemon and local image {IMAGE}")


def test_real_container_lifecycle() -> None:
    runtime = Runtime(DockerAdapter(default_image=IMAGE))
    tools = {t.name: t.fn for t in asyncio.run(create_tool_catalog(runtime).list_tools())}
    env_id = asyncio.run(tools["sandbox.provision"]()).data.environment.env_id
    try:
        assert env_id in _docker("ps", "-q", "--no-trunc", "--filter", f"name={env_id}").stdout or \
            _docker("inspect", "--format", "{{.State.Running}}", env_id).stdout.strip() == "true"
        out = asyncio.run(tools["sandbox.execute"](env_id=env_id, command="echo hello-smoke")).data
        assert out.exit_code == 0 and "hello-smoke" in out.stdout
        assert asyncio.run(tools["sandbox.terminate"](env_id=env_id)).ok
        assert _docker("inspect", env_id).returncode != 0  # container is gone
        refused = asyncio.run(tools["sandbox.execute"](env_id=env_id, command="echo nope"))
        assert refused.error == "environment_terminated"
    finally:
        _docker("rm", "-f", env_id)
