"""LocalStack sandbox adapter — AWS service emulator via docker compose.

Implements SandboxPort using a LocalStack container + awscli sidecar.
Supports both `docker compose exec` and direct `docker exec` fallback.
"""
from __future__ import annotations

import logging
import os
import time
import uuid
from pathlib import Path
from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:
    from ..models import ServiceMockConfig

logger = logging.getLogger(__name__)

_AWSCLI_SVC = "awscli"
_AWSCLI_CONTAINER = "companion_x-awscli-1"
_SHELL = "/bin/sh"


def _has_compose() -> bool:
    """Check if docker compose plugin is available."""
    code, _, _ = _run(["docker", "compose", "version"], timeout=5)
    return code == 0


def _run(cmd: list[str], timeout: int = 60, cwd: str | None = None) -> tuple[int, str, str]:
    import subprocess
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, cwd=cwd)
        return r.returncode, r.stdout, r.stderr
    except subprocess.TimeoutExpired:
        return 1, "", "Command timed out"
    except FileNotFoundError:
        return 1, "", "docker CLI not found"


class LocalStackAdapter:
    """SandboxPort implementation using LocalStack docker-compose."""

    def __init__(self, compose_dir: str | None = None) -> None:
        self._env_id: str | None = None
        self._compose_dir = (
            compose_dir
            or os.environ.get("LOCALSTACK_COMPOSE_DIR")
            or "."
        )
        self._use_compose = _has_compose()
        self._awscli_container = os.environ.get(
            "AWSCLI_CONTAINER", _AWSCLI_CONTAINER,
        )

    async def provision(self, config: dict[str, Any]) -> str:
        if self._env_id:
            return self._env_id
        env_id = f"localstack-{uuid.uuid4().hex[:8]}"
        code, _, stderr = _run(
            ["docker", "compose", "up", "-d", "--wait"],
            timeout=120, cwd=self._compose_dir,
        )
        if code != 0:
            raise RuntimeError(f"LocalStack provision failed: {stderr.strip()}")
        self._env_id = env_id
        logger.info("Provisioned LocalStack env %s", env_id)
        return env_id

    async def terminate(self, env_id: str) -> None:
        _run(["docker", "compose", "down", "-v"], timeout=60, cwd=self._compose_dir)
        self._env_id = None
        logger.info("Terminated LocalStack env %s", env_id)

    async def get_status(self, env_id: str) -> dict[str, Any]:
        code, stdout, _ = _run(
            ["docker", "compose", "exec", "localstack",
             "curl", "-sf", "http://localhost:4566/_localstack/health"],
            timeout=10, cwd=self._compose_dir,
        )
        if code != 0:
            return {"status": "unknown"}
        return {"status": "running", "health": stdout.strip(),
                "public_ip": None, "private_ip": None}

    async def execute(
        self, env_id: str, command: str, timeout_seconds: int = 300,
    ) -> dict[str, Any]:
        start = time.monotonic()
        if self._use_compose:
            cmd = ["docker", "compose", "exec", "-T",
                   _AWSCLI_SVC, _SHELL, "-c", command]
            kw = {"timeout": timeout_seconds, "cwd": self._compose_dir}
        else:
            cmd = ["docker", "exec", self._awscli_container,
                   _SHELL, "-c", command]
            kw = {"timeout": timeout_seconds}
        code, stdout, stderr = _run(cmd, **kw)
        elapsed_ms = int((time.monotonic() - start) * 1000)
        return {"exit_code": code, "stdout": stdout,
                "stderr": stderr, "duration_ms": elapsed_ms}

    async def upload_file(
        self, env_id: str, local_path: str, remote_path: str,
    ) -> dict[str, Any]:
        code, _, stderr = _run(
            ["docker", "compose", "cp", local_path,
             f"{_AWSCLI_SVC}:{remote_path}"], cwd=self._compose_dir)
        return {"success": code == 0, "error": stderr.strip() if code else ""}

    async def download_file(
        self, env_id: str, remote_path: str, local_path: str,
    ) -> dict[str, Any]:
        code, _, stderr = _run(
            ["docker", "compose", "cp",
             f"{_AWSCLI_SVC}:{remote_path}", local_path], cwd=self._compose_dir)
        return {"success": code == 0, "error": stderr.strip() if code else ""}

    async def list_files(self, env_id: str, path: str = "/") -> list[dict[str, Any]]:
        code, stdout, _ = _run(
            ["docker", "compose", "exec", "-T", _AWSCLI_SVC, "ls", "-la", path],
            cwd=self._compose_dir)
        if code != 0:
            return []
        files: list[dict[str, Any]] = []
        for line in stdout.strip().splitlines()[1:]:
            parts = line.split()
            if len(parts) < 2 or parts[-1] in (".", ".."):
                continue
            files.append({"name": parts[-1],
                          "path": f"{path}/{parts[-1]}".replace("//", "/"),
                          "is_directory": parts[0].startswith("d")})
        return files

    def health_check(self) -> dict[str, Any]:
        code, stdout, _ = _run(
            ["docker", "compose", "ps", "--format", "json"],
            timeout=10, cwd=self._compose_dir,
        )
        return {"healthy": code == 0, "adapter": "localstack",
                "compose_dir": self._compose_dir}

    async def apply_service_mocks(
        self, env_id: str, config: ServiceMockConfig,
    ) -> dict[str, Any]:
        """Apply service mock configuration to the sandbox."""
        results: dict[str, Any] = {"env_id": env_id, "mocks_applied": []}

        # Credential store: set AWS credentials for each material set
        if config.credential_store.enabled:
            for name, creds in config.credential_store.material_sets.items():
                acct = creds.get("aws_account_id", "000000000000")
                cmd = (
                    f"export AWS_ACCESS_KEY_ID={acct} && "
                    f"export AWS_SECRET_ACCESS_KEY=test && "
                    f"echo 'Credential store mock: {name} -> account {acct}'"
                )
                await self.execute(env_id, cmd)
            results["mocks_applied"].append({
                "type": "credential_store",
                "material_sets": list(config.credential_store.material_sets.keys()),
            })

        # Credential file: create empty credential files
        if config.credential_file.enabled:
            for path in config.credential_file.credential_paths:
                cmd = f"mkdir -p $(dirname {path}) && touch {path}"
                await self.execute(env_id, cmd)
            results["mocks_applied"].append({
                "type": "credential_file",
                "paths": config.credential_file.credential_paths,
            })

        # OAuth provider: log bypass mode (actual bypass is app-level config)
        if config.oauth_provider.enabled:
            results["mocks_applied"].append({
                "type": "oauth_provider",
                "bypass_mode": config.oauth_provider.bypass_mode,
                "note": "App-level config disables OAuth provider validation",
            })

        # Authorizer: log bypass mode (actual bypass is app-level config)
        if config.authorizer.enabled:
            results["mocks_applied"].append({
                "type": "authorizer",
                "service_name": config.authorizer.service_name,
                "bypass_mode": config.authorizer.bypass_mode,
                "note": "App-level config disables authorizer validation",
            })

        # RPC service: log stub config (WireMock setup is future work)
        if config.rpc_service.enabled:
            results["mocks_applied"].append({
                "type": "rpc_service",
                "stubs": len(config.rpc_service.service_stubs),
                "note": "WireMock stub deployment is future work",
            })

        return results
