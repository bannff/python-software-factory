"""Squad Registry — deployable team-of-agents configs.

Mirrors ``AgentRegistry``: seeds built-in ``SQUADS_TYPED`` (CODE) FIRST, then
overlays user/authored squads from ``<config_dir>/*.yaml`` (each a
``kind="squad"`` ``SquadConfig``). Built-ins WIN on id collision. ``self.squads``
is keyed by id; ``get`` returns the typed model.

A squad is a deploy spec, not an executable graph — it is intentionally kept
out of the ``RegistryConfig`` union and gets its own registry here.
"""
from __future__ import annotations

import logging
from pathlib import Path

import yaml

from ..runtime.registry_contracts import SquadConfig

logger = logging.getLogger(__name__)

__all__ = ["SquadConfig", "SquadRegistry"]


class SquadRegistry:
    """Registry for deployable squad configurations."""

    def __init__(self, config_dir: Path | str):
        self.config_dir = Path(config_dir)
        self.squads: dict[str, SquadConfig] = {}

    async def load(self) -> None:
        """Seed built-in squads, then overlay persisted user squads."""
        from .defaults_squads import SQUADS_TYPED

        merged: dict[str, SquadConfig] = {}
        builtin_ids = {cfg.id for cfg in SQUADS_TYPED}
        for cfg in SQUADS_TYPED:
            merged[cfg.id] = cfg
        if self.config_dir.exists():
            for config_file in sorted(self.config_dir.glob("*.yaml")):
                try:
                    raw = yaml.safe_load(config_file.read_text())
                    if not raw:
                        continue
                    cfg = SquadConfig.model_validate(raw)
                    if cfg.id in builtin_ids:
                        logger.warning(
                            "user squad %r shadows a built-in id; built-in wins",
                            cfg.id,
                        )
                        continue
                    merged[cfg.id] = cfg
                except Exception as exc:  # noqa: BLE001 - skip bad file, keep loading
                    logger.warning("Failed to load squad %s: %s", config_file, exc)
        self.squads = merged

    def get(self, squad_id: str) -> SquadConfig | None:
        """Get squad configuration by ID."""
        return self.squads.get(squad_id)

    def list_squads(self) -> list[dict]:
        """List all registered squads (dict shape for the MCP surface)."""
        return [
            {"id": cfg.id, "name": cfg.name, "description": cfg.description,
             "target_language": cfg.target_language,
             "sandbox_profile": cfg.sandbox_profile}
            for cfg in self.squads.values()
        ]
