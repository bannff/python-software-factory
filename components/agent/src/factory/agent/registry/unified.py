"""Unified persona registry — ONE read path for agent personas
(bd:python-factory-d4roe.1, meta-architect verdict ``9d6a73fb`` Q2).

Before this module there were TWO disjoint sources of persona truth:
the import-time ``AGENTS_TYPED`` list (what the chat resolver read) and
the disk-backed ``AgentRegistry.agents`` dict (what authoring wrote to).
A runtime-authored agent landed in the latter but was invisible to the
former, so it could never back a chat persona.

This module collapses them. Built-ins stay CODE (``AGENTS_TYPED`` is the
immutable seed); user-created agents are DATA behind a ``RegistryStore``
(``runtime/ports.py``). ``merge_personas`` seeds built-ins FIRST then
overlays the store, with built-ins WINNING on id collision (a user may
not shadow a built-in id). ``unified_personas`` is the single read path
both the chat resolver and the discovery surface call.

Default-store seam: ``set_default_store`` wires a process-wide store so
the free-function resolver (which has no ``SuperAgent`` handle) sees the
same user personas the ``AgentRegistry`` does. Default is ``None`` →
only built-ins resolve → ``companion-x-default`` is byte-identical
whether or not any store exists.
"""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from ..runtime.registry_contracts import AgentConfig

if TYPE_CHECKING:
    from ..runtime.ports import RegistryStore

logger = logging.getLogger(__name__)

__all__ = [
    "merge_personas",
    "unified_personas",
    "set_default_store",
    "get_default_store",
    "reset_default_store",
]

# Process-wide store for user-created personas. ``None`` = built-ins
# only (byte-identical default). Production composition roots
# (``SuperAgent.initialize`` / server ``_get_default_agent``) set this
# to the live ``AgentRegistry`` store so resolver + discovery agree.
_default_store: "RegistryStore | None" = None


def merge_personas(
    builtins: list[AgentConfig],
    store_personas: list[AgentConfig],
) -> list[AgentConfig]:
    """Seed ``builtins`` FIRST, then overlay ``store_personas``.

    Built-ins WIN on id collision — a user persona whose id shadows a
    built-in is rejected (logged + skipped), never the other way round.
    Built-in order is preserved; user-only personas append after.
    """
    merged: dict[str, AgentConfig] = {}
    builtin_ids = {b.id for b in builtins}
    for cfg in builtins:
        merged[cfg.id] = cfg
    for cfg in store_personas:
        if cfg.id in builtin_ids:
            logger.warning(
                "user persona %r shadows a built-in id; built-in wins "
                "(user persona ignored)", cfg.id,
            )
            continue
        merged[cfg.id] = cfg
    return list(merged.values())


def unified_personas() -> list[AgentConfig]:
    """The single persona read path: built-ins + the default store.

    Reads ``AGENTS_TYPED`` live so in-process registrations (tests,
    bootstrap) are visible, and overlays the process-wide store.
    """
    from .defaults import AGENTS_TYPED
    store = _default_store
    store_personas = store.load_personas() if store is not None else []
    return merge_personas(list(AGENTS_TYPED), store_personas)


def set_default_store(store: "RegistryStore | None") -> None:
    """Wire the process-wide user-persona store (seam for AgentCore)."""
    global _default_store
    _default_store = store


def get_default_store() -> "RegistryStore | None":
    """Return the process-wide user-persona store (``None`` if unset)."""
    return _default_store


def reset_default_store() -> None:
    """Clear the process-wide store (test hygiene → built-ins only)."""
    global _default_store
    _default_store = None
