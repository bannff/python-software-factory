"""Container launch assembly for the Docker Sandbox adapter."""
from __future__ import annotations

import logging
import uuid
from typing import Any

logger = logging.getLogger(__name__)
_DEFAULT_IMAGE = "ubuntu:22.04"


def _run(*args, **kwargs):
    """Delegate to the adapter's ``_run`` (monkeypatch target preserved)."""
    from . import docker_adapter

    return docker_adapter._run(*args, **kwargs)

class DockerProvisionMixin:
    """Container provisioning for DockerAdapter."""

    async def _provision(self, config: dict[str, Any]) -> str:
        """Provision a new Docker container.

        Supports profile-based config: ports, entrypoint, container_name,
        env_vars. Falls back to random name + sleep infinity for backward compat.
        """
        image = config.get("image", self._default_image)
        container_name = config.get("container_name", f"sandbox-{uuid.uuid4().hex[:8]}")
        secret_mounts = config.get("secret_mounts", ())
        if secret_mounts:
            if config.get("auto_terminate", True) is not True:
                raise ValueError("Secret mounts require auto-termination")
            timeout_seconds = config.get("timeout_seconds", 3600)
            if type(timeout_seconds) is not int or not 60 <= timeout_seconds <= 86400:
                raise ValueError("Secret mounts require a timeout from 60 to 86400 seconds")
            import json

            from ..secret_launch import (
                validate_secret_image_entrypoint,
                validate_secret_launch,
            )

            validate_secret_launch(image, config.get("entrypoint"))
            # An image name or registry digest can be replaced or pulled. A
            # local image ID is immutable and must already exist on this host.
            code, image_id, _ = _run([
                "docker", "image", "inspect", "--format", "{{.Id}}", image,
            ])
            if code != 0 or image_id.strip() != image:
                raise ValueError("Secret mount requires an available local image ID")
            code, image_entrypoint, _ = _run([
                "docker", "image", "inspect", "--format",
                "{{json .Config.Entrypoint}}", image,
            ])
            if code != 0:
                raise ValueError("Secret mount requires a trusted fixed image ENTRYPOINT")
            try:
                validate_secret_image_entrypoint(json.loads(image_entrypoint))
            except (TypeError, ValueError) as exc:
                raise ValueError(
                    "Secret mount requires a trusted fixed image ENTRYPOINT"
                ) from exc
        # Validate the whole network boundary before replacement/removal or
        # network creation. Profiles and direct adapter callers share this.
        from ..peer_network import validate_peer_network

        peer_network = validate_peer_network(config.get("peer_network"))
        if secret_mounts and (
            config.get("replace_existing", True)
            or peer_network is None or not peer_network.internal
            or config.get("ports")
        ):
            raise ValueError(
                "Secret mounts require a new container on an internal peer network without published ports"
            )
        if peer_network is not None and peer_network.internal and config.get("ports"):
            raise ValueError(
                "Internal peer networks cannot publish ports to the host"
            )
        device_labels: dict[str, str] = {}
        if config.get("device_labels") is not None:
            from ..device_presets import DeviceRunLabels

            device_labels = DeviceRunLabels.model_validate(
                config["device_labels"]
            ).docker_labels()

        if config.get("replace_existing", True):
            # Legacy profiles intentionally replace a container with this name.
            if peer_network is not None:
                self._ensure_peer_network(peer_network)
                self._assert_peer_alias_available(peer_network, container_name)
            _run(["docker", "rm", "-f", container_name], timeout=10)
        else:
            code, _, _ = _run(
                ["docker", "container", "inspect", container_name], timeout=10,
            )
            if code == 0:
                raise RuntimeError(
                    f"Container {container_name!r} already exists; "
                    "terminate it explicitly before provisioning again"
                )
            if peer_network is not None:
                self._ensure_peer_network(peer_network)
                self._assert_peer_alias_available(peer_network, container_name)

        from .secret_mounts import build_secret_mount_args
        from .uds_mount import build_mount_args, proxy_env

        cmd = ["docker", "run", "-d", "--name", container_name,
               "--label", "factory.sandbox=true"]
        if peer_network is not None:
            for key, value in {
                "factory.sandbox.peer_network_id": peer_network.network_id,
                "factory.sandbox.peer_network_name": peer_network.docker_network_name,
                "factory.sandbox.peer_alias": peer_network.alias,
                "factory.sandbox.peer_port": str(peer_network.port),
                "factory.sandbox.peer_internal": str(peer_network.internal).lower(),
            }.items():
                cmd.extend(["--label", f"{key}={value}"])
        if secret_mounts:
            # Non-sensitive marker lets execution suppress output even if the
            # local environment metadata store is unavailable after restart.
            cmd.extend([
                "--label", "factory.sandbox.secret_output_suppressed=true",
                "--label", f"factory.sandbox.timeout_seconds={timeout_seconds}",
            ])
        for key, value in device_labels.items():
            cmd.extend(["--label", f"{key}={value}"])
        if platform := config.get("platform"):
            cmd.extend(["--platform", platform])
        if cpus := config.get("cpus"):
            cmd.extend(["--cpus", str(cpus)])
        if memory_mb := config.get("memory_mb"):
            cmd.extend(["--memory", f"{memory_mb}m"])
        if peer_network is not None:
            cmd.extend(["--network", peer_network.docker_network_name])
            cmd.extend(["--network-alias", peer_network.alias])
        if policy_id := config.get("env_vars", {}).get("MCP_POLICY_ID"):
            cmd.extend(["--label", f"factory.workload={policy_id}"])
        cmd.extend(build_mount_args(config))
        cmd.extend(build_secret_mount_args(secret_mounts))

        for host_port, ctr_port in config.get("ports", {}).items():
            cmd.extend(["-p", f"{host_port}:{ctr_port}"])

        for key, value in {**config.get("env_vars", {}), **proxy_env(config)}.items():
            cmd.extend(["-e", f"{key}={value}"])

        cmd.append(image)

        entrypoint = config.get("entrypoint")
        if entrypoint:
            cmd.extend(entrypoint)
        elif not config.get("ports"):
            # No profile ports → legacy mode: keep container alive
            cmd.extend(["sleep", "infinity"])

        code, stdout, stderr = _run(cmd, timeout=60)
        if code != 0:
            if peer_network is not None:
                self._remove_empty_owned_peer_network(
                    peer_network.docker_network_name,
                )
            if secret_mounts:
                # Docker diagnostics can echo bind source paths. Do not expose
                # those host paths through Sandbox logs or the MCP error.
                logger.error("Docker provision failed with a configured secret mount")
                raise RuntimeError(
                    "Docker provision failed while attaching a configured secret"
                )
            logger.error("Docker provision failed: %s", stderr)
            raise RuntimeError(f"Docker provision failed: {stderr.strip()}")

        container_id = stdout.strip()
        self._containers[container_name] = {
            "container_id": container_id,
            "image": image,
            "status": "running",
        }
        if peer_network is not None:
            self._containers[container_name]["peer_network"] = peer_network.public_metadata()
        logger.info("Provisioned container %s (%s)", container_name, image)
        return container_name

