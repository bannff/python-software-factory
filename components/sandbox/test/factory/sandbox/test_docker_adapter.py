"""Tests for DockerAdapter sandbox lifecycle.

Skips if Docker daemon is not available.
Tests provision, execute, file ops, and terminate against real containers.
"""

import asyncio
import subprocess

import pytest

from factory.sandbox.runtime.adapters.docker_adapter import DockerAdapter


def _docker_available() -> bool:
    """Check if Docker daemon is reachable."""
    try:
        result = subprocess.run(
            ["docker", "info"], capture_output=True, timeout=5,
        )
        return result.returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False


def _run_async(coro):
    """Run an async coroutine synchronously."""
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None
    if loop is None:
        return asyncio.run(coro)
    return loop.run_until_complete(coro)


pytestmark = pytest.mark.skipif(
    not _docker_available(), reason="Docker daemon not available",
)


class TestDockerAdapterHealth:
    """Health check tests."""

    def test_health_check_reports_healthy(self):
        adapter = DockerAdapter()
        health = adapter.health_check()
        assert health["healthy"] is True
        assert health["adapter"] == "docker"
        assert "docker_version" in health


class TestDockerAdapterLifecycle:
    """Full lifecycle: provision → execute → terminate."""

    def test_provision_and_terminate(self):
        adapter = DockerAdapter(default_image="alpine:latest")
        env_id = _run_async(adapter.provision({"image": "alpine:latest"}))
        assert env_id.startswith("sandbox-")

        status = _run_async(adapter.get_status(env_id))
        assert status["status"] == "running"

        _run_async(adapter.terminate(env_id))

    def test_execute_command(self):
        adapter = DockerAdapter(default_image="alpine:latest")
        env_id = _run_async(adapter.provision({"image": "alpine:latest"}))
        try:
            result = _run_async(adapter.execute(env_id, "echo hello"))
            assert result["exit_code"] == 0
            assert "hello" in result["stdout"]
            assert result["duration_ms"] >= 0
        finally:
            _run_async(adapter.terminate(env_id))

    def test_execute_failing_command(self):
        adapter = DockerAdapter(default_image="alpine:latest")
        env_id = _run_async(adapter.provision({"image": "alpine:latest"}))
        try:
            result = _run_async(adapter.execute(env_id, "false"))
            assert result["exit_code"] != 0
        finally:
            _run_async(adapter.terminate(env_id))

    def test_list_files(self):
        adapter = DockerAdapter(default_image="alpine:latest")
        env_id = _run_async(adapter.provision({"image": "alpine:latest"}))
        try:
            files = _run_async(adapter.list_files(env_id, "/"))
            assert isinstance(files, list)
            assert len(files) > 0
            names = [f["name"] for f in files]
            assert "etc" in names or "bin" in names
        finally:
            _run_async(adapter.terminate(env_id))

    def test_upload_and_execute(self):
        """Upload a file then verify it exists inside the container."""
        import tempfile
        import os

        adapter = DockerAdapter(default_image="alpine:latest")
        env_id = _run_async(adapter.provision({"image": "alpine:latest"}))
        try:
            # Create a temp file to upload
            with tempfile.NamedTemporaryFile(
                mode="w", suffix=".txt", delete=False,
            ) as f:
                f.write("test content from docker adapter test")
                tmp_path = f.name

            result = _run_async(
                adapter.upload_file(env_id, tmp_path, "/tmp/test.txt"),
            )
            assert result["success"] is True

            # Verify file exists inside container
            exec_result = _run_async(
                adapter.execute(env_id, "cat /tmp/test.txt"),
            )
            assert exec_result["exit_code"] == 0
            assert "test content" in exec_result["stdout"]

            os.unlink(tmp_path)
        finally:
            _run_async(adapter.terminate(env_id))

    def test_status_after_terminate(self):
        adapter = DockerAdapter(default_image="alpine:latest")
        env_id = _run_async(adapter.provision({"image": "alpine:latest"}))
        _run_async(adapter.terminate(env_id))
        # Container is removed, so status should be unknown
        status = _run_async(adapter.get_status(env_id))
        # docker inspect on removed container returns non-zero
        assert status["status"] in ("unknown", "terminated")
