"""Build the adapter config + metadata for a provision call."""
from __future__ import annotations
import re
from typing import Any
from uuid import uuid4
from .models import SandboxConfig
from .secret_launch import validate_secret_launch

def build_provision_context(
    cfg: SandboxConfig, profile: str | None, device_preset: str | None = None,
    peer_network: Any | None = None,
) -> tuple[dict[str, Any], dict[str, Any], list[str]]:
    """Return ``(adapter_config, metadata, setup_commands)`` for ``cfg``.

    Mutates ``cfg.instance_type`` to ``"docker"`` when a profile is resolved,
    preserving the original in-place behavior the caller relies on.
    """
    adapter_config = cfg.model_dump()
    metadata: dict[str, Any] = {
        "timeout_seconds": cfg.timeout_seconds,
        "auto_terminate": cfg.auto_terminate,
    }
    setup_commands: list[str] = []
    if device_preset is not None and not profile:
        raise ValueError("A device_preset requires a sandbox profile")
    if peer_network is not None and not profile:
        raise ValueError("A peer_network requires a sandbox profile")
    if profile:
        from .profiles import resolve_profile
        p = resolve_profile(profile)
        from .peer_network import validate_peer_network

        selected_peer_network = validate_peer_network(
            peer_network if peer_network is not None else p.peer_network,
        )
        if selected_peer_network is not None and selected_peer_network.internal and p.ports:
            raise ValueError(
                "Internal peer networks cannot publish profile ports to the host"
            )
        preset = None
        if device_preset is not None:
            from .device_presets import (
                DeviceRunLabels, preset_sha256, resolve_device_preset,
            )
            from .profile_store import assert_valid_profile_name

            assert_valid_profile_name(profile)
            if p.name != profile:
                raise ValueError("Selected profile name must match its registry slug")
            preset = resolve_device_preset(device_preset)
            if p.device_target is not None:
                raise ValueError("device_target is ambiguous with device_preset")
            if p.ports:
                raise ValueError(
                    "Device preset runs require a profile without fixed host ports"
                )
            for field in ("platform", "cpus", "memory_mb"):
                profile_value = getattr(p, field)
                preset_value = getattr(preset.proxy, field)
                if profile_value is not None and profile_value != preset_value:
                    raise ValueError(
                        f"Profile {field} conflicts with device preset {device_preset}"
                    )
        adapter_config.update({
            "image": p.image, "ports": p.ports,
            "entrypoint": p.entrypoint, "container_name": p.container_name,
            "replace_existing": p.replace_existing,
            "env_vars": p.env_vars,
            "platform": p.platform, "cpus": p.cpus,
            "memory_mb": p.memory_mb,
        })
        if selected_peer_network is not None:
            adapter_config["peer_network"] = selected_peer_network.model_dump()
            metadata["peer_network"] = selected_peer_network.public_metadata()
        if p.secret_refs:
            if p.replace_existing:
                raise ValueError(
                    "Sandbox profiles with secret_refs must not replace existing containers"
                )
            if selected_peer_network is None or not selected_peer_network.internal:
                raise ValueError(
                    "Sandbox profiles with secret_refs require an internal peer network"
                )
            validate_secret_launch(p.image, p.entrypoint)
            if p.setup_commands:
                raise ValueError(
                    "Sandbox profiles with secret_refs cannot define setup_commands"
                )
            # The source paths exist only in this transient adapter config;
            # profile and public runtime metadata retain symbolic names only.
            from .adapters.secret_mounts import resolve_secret_mounts

            adapter_config["secret_mounts"] = resolve_secret_mounts(p.secret_refs)
        cfg.instance_type = "docker"
        setup_commands = list(p.setup_commands)
        metadata.update({
            "profile": p.name,
            "image": p.image,
            "ports": p.ports,
            "health_check_url": p.health_check_url,
            "container_name": p.container_name,
            "shell": p.shell,
            "platform": p.platform, "cpus": p.cpus,
            "memory_mb": p.memory_mb,
            "device_target": (
                p.device_target.model_dump() if p.device_target else None
            ),
        })
        if p.secret_refs:
            # Durable but non-sensitive marker used to suppress command output
            # after the environment is reloaded from its store.
            metadata["secret_mounts_enabled"] = True
        if preset is not None:
            # A selected target is a new instance of the image recipe, never
            # a request to replace an existing container of the same profile.
            if len(p.container_name) > 242 or not re.fullmatch(
                r"[a-zA-Z0-9][a-zA-Z0-9_.-]*", p.container_name,
            ):
                raise ValueError("Profile container_name is unsafe for a device run")
            container_name = f"{p.container_name}-{uuid4().hex[:12]}"
            adapter_config.update({
                "container_name": container_name,
                "replace_existing": False,
                **preset.proxy.model_dump(),
                "device_labels": DeviceRunLabels(
                    profile=profile,
                    device_preset=preset.name,
                    fidelity=preset.fidelity,
                    preset_sha256=preset_sha256(preset),
                    **preset.proxy.model_dump(),
                ).model_dump(),
            })
            metadata.update({
                "container_name": container_name,
                "platform": preset.proxy.platform,
                "cpus": preset.proxy.cpus,
                "memory_mb": preset.proxy.memory_mb,
                "device_preset": preset.model_dump(),
                "preset_sha256": preset_sha256(preset),
            })
    elif cfg.ami_id:
        metadata["ami_id"] = cfg.ami_id

    # Bake default OTEL into every container so anything running inside
    # (builds, tests, a deployed agent squad) exports back to the parent
    # collector. Explicit profile env wins over the defaults.
    from .observability import default_otel_env
    otel_env = default_otel_env(
        adapter_config.get("container_name", "sandbox"),
        metadata.get("profile"),
    )
    if otel_env:
        existing_env = dict(adapter_config.get("env_vars", {}) or {})
        adapter_config["env_vars"] = {**otel_env, **existing_env}
        metadata["otel_enabled"] = True
    return adapter_config, metadata, setup_commands
