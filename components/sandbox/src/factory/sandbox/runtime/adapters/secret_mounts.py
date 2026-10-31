"""Resolve trusted secret references to fixed, read-only Docker mounts.

Only names are stored in Sandbox profiles. Host paths are resolved from the
Sandbox server's process environment immediately before Docker provisioning and
are passed only to Docker's mount arguments.
"""
from __future__ import annotations

import os
import stat
from dataclasses import dataclass
from pathlib import Path
from typing import Literal, Mapping, Sequence

SecretRef = Literal["ditto-offline-license"]

DITTO_LICENSE_ENV = "SANDBOX_SECRET_DITTO_OFFLINE_LICENSE_FILE"
DITTO_LICENSE_TARGET = "/run/secrets/ditto-offline-license"


@dataclass(frozen=True)
class ResolvedSecretMount:
    """Internal-only host source and fixed container destination."""

    reference: SecretRef
    source: Path

    @property
    def target(self) -> str:
        if self.reference == "ditto-offline-license":
            return DITTO_LICENSE_TARGET
        raise ValueError("Unsupported Sandbox secret reference")


def resolve_secret_mounts(
    references: Sequence[SecretRef],
    environ: Mapping[str, str] | None = None,
) -> tuple[ResolvedSecretMount, ...]:
    """Resolve allowlisted names using host-only configuration.

    Error messages intentionally omit configured paths. The resulting objects
    are transient Docker adapter input and must never be serialized as runtime
    metadata, events, profile data, or MCP output.
    """
    host_env = os.environ if environ is None else environ
    result: list[ResolvedSecretMount] = []
    for reference in references:
        if reference != "ditto-offline-license":
            raise ValueError("Unsupported Sandbox secret reference")
        configured_path = host_env.get(DITTO_LICENSE_ENV)
        if not configured_path:
            raise ValueError("Configured Sandbox secret is unavailable")
        try:
            source = Path(configured_path).expanduser().resolve(strict=True)
            if not stat.S_ISREG(source.stat().st_mode):
                raise ValueError
        except (OSError, RuntimeError, ValueError):
            raise ValueError(
                "Configured Sandbox secret must resolve to a regular file"
            ) from None
        result.append(ResolvedSecretMount(reference=reference, source=source))
    return tuple(result)


def build_secret_mount_args(
    mounts: Sequence[ResolvedSecretMount],
) -> list[str]:
    """Create fixed-target, read-only bind arguments for resolved refs."""
    args: list[str] = []
    for mount in mounts:
        # Docker's --mount syntax uses commas as separators. Reject paths it
        # cannot represent safely instead of producing a different mount.
        if "," in str(mount.source):
            raise ValueError(
                "Configured Sandbox secret path cannot be represented safely"
            )
        args.extend([
            "--mount",
            f"type=bind,source={mount.source},target={mount.target},readonly",
        ])
    return args


__all__ = [
    "DITTO_LICENSE_ENV", "DITTO_LICENSE_TARGET", "ResolvedSecretMount",
    "SecretRef", "build_secret_mount_args", "resolve_secret_mounts",
]
