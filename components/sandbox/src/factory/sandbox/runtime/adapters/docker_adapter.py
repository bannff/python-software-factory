"""Docker sandbox adapter — runs commands in Docker containers.

Implements SandboxPort against the local Docker daemon. Each environment =
one container. Provision pulls/runs an image, execute runs commands inside
it, terminate stops and removes it. Large operation families live in the
DockerProvisionMixin, DockerPeerNetworkMixin, and DockerFileOpsMixin.
"""
from __future__ import annotations

import logging
from functools import wraps
from pathlib import Path
from typing import Any

from .docker_file_ops import DockerFileOpsMixin
from .docker_peer_lock import peer_network_provision_lock
from .docker_peer_network import DockerPeerNetworkMixin
from .docker_provision import DockerProvisionMixin
from .docker_runner import run as _docker_run

logger = logging.getLogger(__name__)

_DEFAULT_IMAGE = "ubuntu:22.04"
_PEER_NETWORK_LOCK_DIR = (
    Path.home() / ".cache" / "python-factory" / "peer-network-locks"
)


def _peer_network_provision_lock(network_name: str):
    """Hold this process's per-network advisory lock (see docker_peer_lock)."""
    return peer_network_provision_lock(network_name, _PEER_NETWORK_LOCK_DIR)


def _serialize_peer_network_provision(method):
    """Hold a cross-process lock for the whole check-and-attach transaction."""
    @wraps(method)
    async def wrapped(self, config):
        from ..peer_network import validate_peer_network

        spec = validate_peer_network(config.get("peer_network"))
        if spec is None:
            return await method(self, config)
        with _peer_network_provision_lock(spec.docker_network_name):
            return await method(self, config)

    return wrapped


def _run(cmd: list[str], timeout: int = 30) -> tuple[int, str, str]:
    """Run a subprocess synchronously, return (exit_code, stdout, stderr)."""
    return _docker_run(cmd, timeout=timeout)


class DockerAdapter(DockerPeerNetworkMixin, DockerProvisionMixin, DockerFileOpsMixin):
    """Docker-backed sandbox implementing SandboxPort."""

    def __init__(self, default_image: str | None = None) -> None:
        self._default_image = default_image or _DEFAULT_IMAGE
        self._containers: dict[str, dict[str, Any]] = {}

    @_serialize_peer_network_provision
    async def provision(self, config: dict[str, Any]) -> str:
        return await self._provision(config)

    async def terminate(self, env_id: str) -> None:
        """Stop and remove a Docker container."""
        peer_network = self._peer_network_for_container(env_id)
        _run(["docker", "rm", "-f", env_id], timeout=30)
        if peer_network is not None:
            self._remove_empty_owned_peer_network(peer_network["network_name"])
        if env_id in self._containers:
            self._containers[env_id]["status"] = "terminated"
        logger.info("Terminated container %s", env_id)

    def sweep_orphans(self) -> list[dict[str, Any]]:
        """Reap crashed/exited labeled containers; return the reaped list."""
        from .uds_mount import sweep_orphans

        return sweep_orphans(_run)

    async def get_status(self, env_id: str) -> dict[str, Any]:
        """Get container status via docker inspect."""
        code, stdout, _ = _run([
            "docker", "inspect", "--format",
            "{{.State.Status}}", env_id,
        ])
        if code != 0:
            return {"status": "unknown"}
        status = stdout.strip()
        result: dict[str, Any] = {
            "status": status, "public_ip": None, "private_ip": None,
        }
        network = self._peer_network_for_container(env_id)
        if network is not None:
            result["peer_network"] = network
        return result

    def get_secret_output_suppression(self, env_id: str) -> bool | None:
        """Read the marker; ``None`` means Docker could not verify the label."""
        code, stdout, _ = _run([
            "docker", "inspect", "--format",
            '{{ index .Config.Labels "factory.sandbox.secret_output_suppressed" }}',
            env_id,
        ])
        if code != 0:
            return None
        marker = stdout.strip()
        if marker == "true":
            return True
        if marker in {"false", "", "<no value>"}:
            return False
        return None

    def health_check(self) -> dict[str, Any]:
        """Check if Docker daemon is reachable."""
        code, stdout, _ = _run(["docker", "info", "--format", "{{.ServerVersion}}"])
        if code != 0:
            return {"healthy": False, "adapter": "docker", "error": "Docker not available"}
        return {
            "healthy": True,
            "adapter": "docker",
            "docker_version": stdout.strip(),
            "active_containers": len(
                [c for c in self._containers.values() if c["status"] == "running"]
            ),
        }
