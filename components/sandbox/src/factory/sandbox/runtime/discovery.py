"""Docker environment discovery for sandbox runtime."""
from __future__ import annotations

from typing import Iterable

from ..core import EnvironmentStatus
from .models import EnvironmentInfo


def _parse_labels(raw: str) -> dict[str, str]:
    labels: dict[str, str] = {}
    for part in raw.split(","):
        if "=" not in part:
            continue
        key, value = part.split("=", 1)
        labels[key.strip()] = value.strip()
    return labels


def _docker_ps_lines(args: Iterable[str]) -> list[str]:
    import subprocess

    result = subprocess.run(
        [
            "docker",
            "ps",
            *args,
            "--format",
            "{{.Names}}\t{{.Status}}\t{{.CreatedAt}}\t{{.Labels}}",
        ],
        capture_output=True,
        text=True,
        timeout=5,
    )
    if result.returncode != 0:
        return []
    return result.stdout.strip().splitlines()


def discover_live_workloads() -> list[dict[str, str]]:
    """Live workload containers (``factory.workload``-labeled), for reconciliation.

    Lists only RUNNING containers carrying the workload label and reports each
    as ``{policy_id, env_id, status}``. This is the live set Workflow diffs
    against; sandbox only reports liveness, it never revokes.
    """
    try:
        lines = _docker_ps_lines(["--filter", "label=factory.workload"])
    except Exception:
        return []
    workloads: list[dict[str, str]] = []
    seen: set[str] = set()
    for line in lines:
        parts = line.split("\t")
        if len(parts) < 2 or parts[0] in seen:
            continue
        seen.add(parts[0])
        labels = _parse_labels(parts[3] if len(parts) > 3 else "")
        policy_id = labels.get("factory.workload")
        if not policy_id:
            continue
        status = "running" if "up" in parts[1].lower() else "unknown"
        workloads.append({
            "policy_id": policy_id, "env_id": parts[0], "status": status,
        })
    return workloads


def discover_docker_envs() -> list[EnvironmentInfo]:
    """Discover running sandbox containers from Docker daemon."""
    try:
        lines = _docker_ps_lines(["--filter", "label=factory.sandbox=true"])
        lines.extend(_docker_ps_lines(["--filter", "label=vuln.target"]))
        lines.extend(_docker_ps_lines(["--filter", "name=localstack"]))
    except Exception:
        return []
    envs: list[EnvironmentInfo] = []
    seen: set[str] = set()
    for line in lines:
        parts = line.split("\t")
        if len(parts) < 2:
            continue
        name = parts[0]
        if name in seen:
            continue
        seen.add(name)
        labels = _parse_labels(parts[3] if len(parts) > 3 else "")
        is_managed = labels.get("factory.sandbox") == "true"
        device_metadata: dict[str, object] = {}
        if labels.get("factory.sandbox.secret_output_suppressed") == "true":
            device_metadata["secret_mounts_enabled"] = True
        if is_managed and "factory.sandbox.device_preset" in labels:
            from .device_presets import DeviceRunLabels

            try:
                target = DeviceRunLabels.from_docker_labels(labels)
            except (KeyError, TypeError, ValueError):
                pass  # Ignore malformed or partial labels from external containers.
            else:
                device_metadata.update({
                    "profile": target.profile,
                    "device_preset": {
                        "name": target.device_preset,
                        "fidelity": target.fidelity,
                        "proxy": {
                            "platform": target.platform,
                            "cpus": target.cpus,
                            "memory_mb": target.memory_mb,
                        },
                    },
                    "platform": target.platform,
                    "cpus": target.cpus,
                    "memory_mb": target.memory_mb,
                })
                if target.preset_sha256 is not None:
                    device_metadata["preset_sha256"] = target.preset_sha256
        status_str = parts[1].lower()
        status = (
            EnvironmentStatus.RUNNING if "up" in status_str
            else EnvironmentStatus.UNKNOWN
        )
        envs.append(EnvironmentInfo(
            env_id=name, status=status, instance_type="docker",
            created_at=parts[2] if len(parts) > 2 else "",
            metadata={
                "discovery_source": "docker",
                "management": "sandbox-managed" if is_managed else "external-compose",
                **device_metadata,
                **{
                    key: value
                    for key, value in labels.items()
                    if key in {
                        "factory.sandbox",
                        "factory.sandbox.secret_output_suppressed",
                        "vuln.target",
                        "vuln.base_url",
                        "com.docker.compose.project",
                        "com.docker.compose.service",
                    }
                },
            },
        ))
    return envs
