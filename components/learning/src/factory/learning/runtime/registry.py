"""Reward-source registry — built-ins-win overlay (bd python-factory-pfvo9).

Mirrors the oracle brick's VerifierRegistry: built-in reward sources are
CODE and WIN on id collision; pack/user sources are DATA registered into
an overlay. Unlike the oracle (which resolves ONE verifier by domain id),
the learning engine iterates ALL registered sources — each decides whether
it has signal — so the public read is ``sources()`` (the union), keyed by
``source_id`` for built-ins-win dedupe. The engine never branches on a
domain literal.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .ports import RewardSourcePort

logger = logging.getLogger(__name__)

__all__ = [
    "RewardSourceRegistry",
    "get_registry",
    "register_reward_source",
    "reset_registry",
]


class RewardSourceRegistry:
    """Built-ins-win overlay of reward sources keyed by ``source_id``."""

    def __init__(self) -> None:
        self._builtins: dict[str, "RewardSourcePort"] = {}
        self._overlay: dict[str, "RewardSourcePort"] = {}

    def register_builtin(self, source: "RewardSourcePort") -> None:
        """Register a CODE built-in source (wins on collision)."""
        sid = getattr(source, "source_id", "")
        if sid:
            self._builtins[sid] = source

    def register(self, source: "RewardSourcePort") -> None:
        """Register a pack/user source into the overlay (built-ins win)."""
        sid = getattr(source, "source_id", "")
        if not sid:
            return
        if sid in self._builtins:
            logger.warning(
                "pack reward source %r shadows a built-in id; built-in "
                "wins (pack source ignored)", sid,
            )
            return
        self._overlay[sid] = source

    def sources(self) -> list["RewardSourcePort"]:
        """All registered sources (built-ins first), built-ins-win dedupe."""
        merged: dict[str, "RewardSourcePort"] = {**self._overlay, **self._builtins}
        return [merged[sid] for sid in sorted(merged)]

    def source_ids(self) -> list[str]:
        """All registered source ids, sorted."""
        return sorted({*self._builtins, *self._overlay})

    def reset(self) -> None:
        """Clear the pack overlay (test hygiene → built-ins only)."""
        self._overlay.clear()


# Process-wide registry. Built-ins are seeded in CODE (runtime.get_runtime);
# packs overlay DATA via register_reward_source.
_registry = RewardSourceRegistry()


def get_registry() -> RewardSourceRegistry:
    """Return the process-wide reward-source registry."""
    return _registry


def register_reward_source(source: "RewardSourcePort") -> None:
    """Pack-facing seam: register a reward source into the overlay."""
    _registry.register(source)


def reset_registry() -> None:
    """Clear the process-wide overlay (test hygiene)."""
    _registry.reset()
