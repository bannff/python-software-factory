"""Immutable, neutral startup composition value objects."""
from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import Mapping


class BlockchainConfigurationError(ValueError):
    """Raised when trusted blockchain startup configuration is invalid."""


_TRUSTED_RUNTIME_FACTORY_IDS = frozenset({"economy"})


@dataclass(frozen=True)
class ProfileDefinition:
    """Server-side declaration of a mounted ledger profile."""

    profile_id: str
    runtime_factory_id: str
    mounted: bool = True


@dataclass(frozen=True)
class ProfileRegistration:
    """Trusted profile definition and its finite supported backend IDs."""

    definition: ProfileDefinition
    backend_ids: tuple[str, ...]


@dataclass(frozen=True)
class BlockchainComposition:
    """Validated immutable startup composition; never request-routed."""

    registrations: Mapping[str, ProfileRegistration]
    active_profile_id: str
    backend_id: str

    @classmethod
    def create(
        cls, registrations: tuple[ProfileRegistration, ...], backend_id: str,
    ) -> "BlockchainComposition":
        by_id: dict[str, ProfileRegistration] = {}
        for registration in registrations:
            definition = registration.definition
            if not definition.profile_id or not definition.runtime_factory_id:
                raise BlockchainConfigurationError("Profile IDs and factories must be non-empty")
            if definition.runtime_factory_id not in _TRUSTED_RUNTIME_FACTORY_IDS:
                raise BlockchainConfigurationError(
                    f"Untrusted runtime factory: {definition.runtime_factory_id}",
                )
            if definition.profile_id in by_id:
                raise BlockchainConfigurationError(f"Duplicate profile ID: {definition.profile_id}")
            if len(registration.backend_ids) != len(set(registration.backend_ids)):
                raise BlockchainConfigurationError(f"Duplicate backend ID for {definition.profile_id}")
            if not registration.backend_ids:
                raise BlockchainConfigurationError(f"No backends configured for {definition.profile_id}")
            by_id[definition.profile_id] = registration
        mounted = [item for item in by_id.values() if item.definition.mounted]
        if len(mounted) != 1 or mounted[0].definition.profile_id != "economy":
            raise BlockchainConfigurationError("Only the economy profile may be mounted")
        active = mounted[0]
        if backend_id not in active.backend_ids:
            allowed = ", ".join(sorted(active.backend_ids))
            raise BlockchainConfigurationError(
                f"Invalid BLOCKCHAIN_ADAPTER={backend_id!r}; allowed: {allowed}",
            )
        return cls(MappingProxyType(by_id), active.definition.profile_id, backend_id)
