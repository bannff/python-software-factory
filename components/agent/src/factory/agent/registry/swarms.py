"""Swarm Registry — loads and manages swarm configurations.

Stores ``SwarmConfig`` Pydantic models. YAML/JSON loaders validate
at load time. ``self.swarms`` is keyed by id; ``get`` returns the
typed model. MCP surface (``list_swarms*``) returns plain dicts via
``.model_dump()``-friendly attribute access.
"""

from pathlib import Path
import json
import logging
import yaml

from ..runtime.registry_contracts import SwarmAgentConfig, SwarmConfig

logger = logging.getLogger(__name__)


__all__ = ["SwarmAgentConfig", "SwarmConfig", "SwarmRegistry"]


class SwarmRegistry:
    """Registry for swarm configurations."""

    def __init__(self, config_dir: Path | str):
        self.config_dir = Path(config_dir)
        self.swarms: dict[str, SwarmConfig] = {}

    async def load(self) -> None:
        """Load all swarm configurations from directory."""
        if not self.config_dir.exists():
            return
        for config_file in self.config_dir.glob("*.yaml"):
            try:
                with open(config_file) as f:
                    raw = yaml.safe_load(f)
                if raw:
                    cfg = SwarmConfig.model_validate(raw)
                    self.swarms[cfg.id] = cfg
            except Exception as e:
                logger.warning("Failed to load %s: %s", config_file, e)
        for config_file in self.config_dir.glob("*.json"):
            try:
                with open(config_file) as f:
                    raw = json.load(f)
                if raw:
                    cfg = SwarmConfig.model_validate(raw)
                    self.swarms[cfg.id] = cfg
            except Exception as e:
                logger.warning("Failed to load %s: %s", config_file, e)

    def get(self, swarm_id: str) -> SwarmConfig | None:
        """Get swarm configuration by ID."""
        return self.swarms.get(swarm_id)

    def list_swarms(self) -> list[dict]:
        """List all registered swarms (dict shape for MCP surface)."""
        return [
            {"id": cfg.id, "name": cfg.name,
             "description": cfg.description,
             "entry_point": cfg.entry_point,
             "agent_count": len(cfg.agents)}
            for cfg in self.swarms.values()
        ]

    def list_swarms_with_schemas(self) -> list[dict]:
        """List all registered swarms with their schemas."""
        return [
            {"id": cfg.id, "name": cfg.name,
             "description": cfg.description,
             "entry_point": cfg.entry_point,
             "agents": [{"id": a.id, "name": a.name} for a in cfg.agents],
             "input_schema": cfg.input_schema,
             "output_schema": cfg.output_schema}
            for cfg in self.swarms.values()
        ]
