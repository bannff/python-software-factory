"""RegistryStore adapters — persistence for USER-created personas
(bd:python-factory-d4roe.1, meta-architect verdict ``9d6a73fb`` Q2).

Built-ins live in CODE (``registry/defaults.py::AGENTS_TYPED``); these
adapters own only the DATA tier. ``DiskRegistryStore`` is the local-dev
backend (the same ``*.yaml`` / ``*.json`` glob ``AgentRegistry.load``
used historically). ``InMemoryRegistryStore`` is a test/in-process
backend AND the clean seam an AgentCore-persistent adapter slots into
later — build the Protocol + these two now, NOT the AgentCore adapter
(out of scope for Phase 0).

Both return the PERSONA contract (``registry_contracts.AgentConfig``),
validated at load so a typo fails fast. Validation failures are logged
and skipped (mirrors the pre-unification ``load`` behavior) so one bad
file never sinks the whole registry.
"""
from __future__ import annotations

import json
import logging
from pathlib import Path

import yaml

from ..registry_contracts import AgentConfig

logger = logging.getLogger(__name__)

__all__ = ["DiskRegistryStore", "InMemoryRegistryStore"]


class DiskRegistryStore:
    """Disk-backed persona store — globs ``*.yaml`` / ``*.json`` from a
    directory and validates each into an ``AgentConfig``.

    Implements ``runtime.ports.RegistryStore``. ``save_persona`` writes
    ``<id>.yaml``; ``delete_persona`` removes any ``<id>.{yaml,json}``.
    A missing directory is treated as empty (no personas) so built-ins
    resolve identically whether or not the store exists on disk.
    """

    def __init__(self, config_dir: Path | str) -> None:
        self.config_dir = Path(config_dir)

    def load_personas(self) -> list[AgentConfig]:
        if not self.config_dir.exists():
            return []
        personas: list[AgentConfig] = []
        for pattern, loader in (("*.yaml", yaml.safe_load), ("*.json", json.load)):
            for config_file in sorted(self.config_dir.glob(pattern)):
                try:
                    with open(config_file) as f:
                        raw = loader(f)
                    if raw:
                        personas.append(AgentConfig.model_validate(raw))
                except Exception as e:  # noqa: BLE001 — skip bad file, keep rest
                    logger.warning("Failed to load %s: %s", config_file, e)
        return personas

    def save_persona(self, config: AgentConfig) -> None:
        self.config_dir.mkdir(parents=True, exist_ok=True)
        target = self.config_dir / f"{config.id}.yaml"
        with open(target, "w") as f:
            yaml.safe_dump(config.model_dump(), f, sort_keys=False)

    def delete_persona(self, agent_id: str) -> bool:
        removed = False
        for suffix in (".yaml", ".json"):
            path = self.config_dir / f"{agent_id}{suffix}"
            if path.exists():
                path.unlink()
                removed = True
        return removed


class InMemoryRegistryStore:
    """In-process persona store — a dict keyed by ``id``.

    Doubles as the reference implementation for the AgentCore seam: a
    persistent backend swaps in by implementing the same three methods.
    Useful in tests that need user-created personas without touching
    disk. Validates inputs so the contract matches the disk adapter.
    """

    def __init__(self, personas: list[AgentConfig] | None = None) -> None:
        self._personas: dict[str, AgentConfig] = {}
        for cfg in personas or []:
            self.save_persona(cfg)

    def load_personas(self) -> list[AgentConfig]:
        return list(self._personas.values())

    def save_persona(self, config: AgentConfig) -> None:
        cfg = config if isinstance(config, AgentConfig) else AgentConfig.model_validate(config)
        self._personas[cfg.id] = cfg

    def delete_persona(self, agent_id: str) -> bool:
        return self._personas.pop(agent_id, None) is not None
