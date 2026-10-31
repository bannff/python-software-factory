"""Secret-aware Docker container file and command operations."""
from __future__ import annotations

from typing import Any

_DEFAULT_SHELL = "/bin/sh"


def _run(*args, **kwargs):
    """Delegate to the adapter's ``_run`` (monkeypatch target preserved)."""
    from . import docker_adapter

    return docker_adapter._run(*args, **kwargs)

class DockerFileOpsMixin:
    """Secret-aware file/command operations for DockerAdapter."""

    async def execute(
        self, env_id: str, command: str, timeout_seconds: int = 300,
    ) -> dict[str, Any]:
        """Execute a command unless secret state is enabled or unverifiable."""
        if self.get_secret_output_suppression(env_id) is not False:
            return {
                "exit_code": 126,
                "stdout": "",
                "stderr": (
                    "Execution is disabled for secret-enabled or unverified sandboxes"
                ),
                "duration_ms": 0,
            }
        import time

        start = time.monotonic()
        code, stdout, stderr = _run(
            ["docker", "exec", env_id, _DEFAULT_SHELL, "-c", command],
            timeout=timeout_seconds,
        )
        elapsed_ms = int((time.monotonic() - start) * 1000)
        return {
            "exit_code": code,
            "stdout": stdout,
            "stderr": stderr,
            "duration_ms": elapsed_ms,
        }


    async def upload_file(
        self, env_id: str, local_path: str, remote_path: str,
    ) -> dict[str, Any]:
        """Copy a file into the container."""
        if self.get_secret_output_suppression(env_id) is not False:
            return {
                "success": False,
                "error": "File operations are disabled for secret-enabled or unverified sandboxes",
            }
        code, _, stderr = _run(
            ["docker", "cp", local_path, f"{env_id}:{remote_path}"],
        )
        if code != 0:
            return {"success": False, "error": stderr.strip()}
        return {"success": True, "remote_path": remote_path}


    async def download_file(
        self, env_id: str, remote_path: str, local_path: str,
    ) -> dict[str, Any]:
        """Copy a file out of the container."""
        if self.get_secret_output_suppression(env_id) is not False:
            return {
                "success": False,
                "error": "File operations are disabled for secret-enabled or unverified sandboxes",
            }
        code, _, stderr = _run(
            ["docker", "cp", f"{env_id}:{remote_path}", local_path],
        )
        if code != 0:
            return {"success": False, "error": stderr.strip()}
        return {"success": True, "local_path": local_path}


    async def list_files(
        self, env_id: str, path: str = "/",
    ) -> list[dict[str, Any]]:
        """List files inside the container."""
        if self.get_secret_output_suppression(env_id) is not False:
            return []
        code, stdout, _ = _run(
            ["docker", "exec", env_id, "ls", "-la", path],
        )
        if code != 0:
            return []
        files: list[dict[str, Any]] = []
        for line in stdout.strip().splitlines()[1:]:  # skip "total" line
            parts = line.split()
            if len(parts) < 2:
                continue
            name = parts[-1]
            if name in (".", ".."):
                continue
            is_dir = parts[0].startswith("d")
            size = 0
            if not is_dir and len(parts) >= 5:
                try:
                    size = int(parts[4])
                except ValueError:
                    size = 0
            files.append({
                "name": name,
                "path": f"{path}/{name}".replace("//", "/"),
                "size_bytes": size,
                "is_directory": is_dir,
            })
        return files


