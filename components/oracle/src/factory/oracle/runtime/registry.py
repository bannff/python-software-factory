"""Verifier registry — built-ins-win overlay (bd python-factory-216ti).

Mirrors the unified persona registry: built-in verifiers are CODE and
WIN on id collision; pack/user verifiers are DATA registered into an
overlay. Resolution is a pure dict lookup keyed by domain/manifest id —
the engine never branches on a domain literal. An unknown id resolves to
``None`` so the runtime degrades to its generic fallback verifier.

Process-wide singleton + ``register_verifier`` free function provide the
pack-facing seam (parallels the persona registry's ``set_default_store``)
so a domain pack can register its verifier without the oracle engine ever
importing the pack.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .ports import VerifierPort

logger = logging.getLogger(__name__)

__all__ = [
    "VerifierRegistry",
    "get_registry",
    "register_verifier",
    "reset_registry",
]


class VerifierRegistry:
    """Built-ins-win overlay of domain verifiers."""

    def __init__(self) -> None:
        self._builtins: dict[str, "VerifierPort"] = {}
        self._overlay: dict[str, "VerifierPort"] = {}

    def register_builtin(self, domain_id: str, verifier: "VerifierPort") -> None:
        """Register a CODE built-in verifier (wins on collision)."""
        if domain_id:
            self._builtins[domain_id] = verifier

    def register(self, domain_id: str, verifier: "VerifierPort") -> None:
        """Register a pack/user verifier into the overlay.

        Built-ins WIN: a pack verifier whose id shadows a built-in is
        logged and skipped, never the other way round.
        """
        if not domain_id:
            return
        if domain_id in self._builtins:
            logger.warning(
                "pack verifier %r shadows a built-in id; built-in wins "
                "(pack verifier ignored)", domain_id,
            )
            return
        self._overlay[domain_id] = verifier

    def resolve(self, domain_id: str) -> "VerifierPort | None":
        """Return the verifier for ``domain_id`` (built-in first), else None."""
        if not domain_id:
            return None
        return self._builtins.get(domain_id) or self._overlay.get(domain_id)

    def domains(self) -> list[str]:
        """All registered domain ids (built-ins + overlay), sorted."""
        return sorted({*self._builtins, *self._overlay})

    def reset(self) -> None:
        """Clear the pack overlay (test hygiene → built-ins only)."""
        self._overlay.clear()


# Process-wide registry. Built-ins are seeded in CODE; packs overlay DATA.
_registry = VerifierRegistry()


def get_registry() -> VerifierRegistry:
    """Return the process-wide verifier registry."""
    return _registry


def register_verifier(domain_id: str, verifier: "VerifierPort") -> None:
    """Pack-facing seam: register a domain verifier into the overlay."""
    _registry.register(domain_id, verifier)


def reset_registry() -> None:
    """Clear the process-wide overlay (test hygiene)."""
    _registry.reset()
