"""Docker bridge ownership and peer endpoint operations."""
from __future__ import annotations

import json
from typing import Any

_RunFn = None  # placeholder replaced below


def _run(*args, **kwargs):
    """Delegate to the adapter's ``_run`` (monkeypatch target preserved)."""
    from . import docker_adapter

    return docker_adapter._run(*args, **kwargs)


class DockerPeerNetworkMixin:
    """Peer-network ownership checks and lifecycle for DockerAdapter."""

    @staticmethod
    def _ensure_peer_network(spec: Any) -> None:
        """Create a managed bridge or require an existing one to be ours."""
        name = spec.docker_network_name
        code, stdout, _ = _run([
            "docker", "network", "inspect", "--format",
            '{{ index .Labels "factory.sandbox.owner" }}|{{.Internal}}', name,
        ])
        if code == 0:
            expected = f"python-factory|{str(spec.internal).lower()}"
            if stdout.strip() != expected:
                raise RuntimeError(
                    f"Docker network {name!r} is not Sandbox-owned or has a different internal mode"
                )
            return
        create = ["docker", "network", "create", "--driver", "bridge"]
        if spec.internal:
            create.append("--internal")
        create.extend([
            "--label", "factory.sandbox=true",
            "--label", "factory.sandbox.owner=python-factory",
            "--label", f"factory.sandbox.peer_network_id={spec.network_id}",
            name,
        ])
        code, _, stderr = _run(create)
        if code != 0:
            # A concurrent provision may have created it; accept only an
            # explicitly Sandbox-owned network after re-inspection.
            check, owner, _ = _run([
                "docker", "network", "inspect", "--format",
                '{{ index .Labels "factory.sandbox.owner" }}|{{.Internal}}', name,
            ])
            expected = f"python-factory|{str(spec.internal).lower()}"
            if check == 0 and owner.strip() == expected:
                return
            raise RuntimeError(f"Could not create Sandbox peer network {name!r}: {stderr.strip()}")

    @staticmethod

    def _assert_peer_alias_available(spec: Any, container_name: str) -> None:
        """Reject aliases already bound by a different attached container."""
        network_name = spec.docker_network_name
        code, stdout, _ = _run([
            "docker", "network", "inspect", "--format",
            "{{json .Containers}}", network_name,
        ])
        if code != 0:
            raise RuntimeError(
                f"Could not verify peer alias on Docker network {network_name!r}"
            )
        import json

        try:
            containers = json.loads(stdout or "{}") or {}
            if not isinstance(containers, dict):
                raise TypeError("Docker network container listing is not an object")
        except (TypeError, ValueError, json.JSONDecodeError) as exc:
            raise RuntimeError(
                f"Could not verify peer alias on Docker network {network_name!r}"
            ) from exc

        for container in containers.values():
            attached_name = container.get("Name") if isinstance(container, dict) else None
            if not attached_name:
                raise RuntimeError(
                    f"Could not verify aliases for a container on {network_name!r}"
                )
            if attached_name == container_name:
                continue
            code, stdout, _ = _run([
                "docker", "inspect", "--format",
                "{{json .NetworkSettings.Networks}}", attached_name,
            ])
            if code != 0:
                raise RuntimeError(
                    f"Could not verify aliases for attached peer {attached_name!r}"
                )
            try:
                networks = json.loads(stdout or "{}") or {}
                network_config = networks.get(network_name)
                aliases = (
                    network_config.get("Aliases")
                    if isinstance(network_config, dict) else None
                )
                if not isinstance(aliases, list) or not all(
                    isinstance(alias, str) for alias in aliases
                ):
                    raise ValueError("Docker network aliases are unavailable")
            except (AttributeError, TypeError, ValueError, json.JSONDecodeError) as exc:
                raise RuntimeError(
                    f"Could not verify aliases for attached peer {attached_name!r}"
                ) from exc
            if spec.alias in aliases:
                raise ValueError(
                    f"Peer alias {spec.alias!r} is already attached to another container"
                )

    @staticmethod

    def _peer_network_for_container(env_id: str) -> dict[str, Any] | None:
        """Read peer endpoint labels from a container, including after restart."""
        code, stdout, _ = _run([
            "docker", "inspect", "--format",
            '{{json .Config.Labels}}', env_id,
        ])
        if code != 0:
            return None
        import json

        try:
            labels = json.loads(stdout)
            raw = {
                "network_id": labels["factory.sandbox.peer_network_id"],
                "alias": labels["factory.sandbox.peer_alias"],
                "port": int(labels["factory.sandbox.peer_port"]),
                "internal": labels["factory.sandbox.peer_internal"] == "true",
            }
            from ..peer_network import validate_peer_network

            spec = validate_peer_network(raw)
        except (KeyError, TypeError, ValueError, json.JSONDecodeError):
            return None
        assert spec is not None
        return spec.public_metadata()

    @staticmethod

    def _remove_empty_owned_peer_network(network_name: str) -> None:
        """Remove only an empty managed bridge; Docker arbitrates races."""
        code, stdout, _ = _run([
            "docker", "network", "inspect", "--format",
            '{{ index .Labels "factory.sandbox.owner" }}|{{json .Containers}}',
            network_name,
        ])
        if code != 0:
            return
        owner, _, attached_json = stdout.strip().partition("|")
        if owner != "python-factory":
            return
        import json

        try:
            attached = json.loads(attached_json)
        except json.JSONDecodeError:
            return
        if attached:
            return
        # If a peer joins after inspect, Docker refuses removal while attached.
        _run(["docker", "network", "rm", network_name], timeout=10)


