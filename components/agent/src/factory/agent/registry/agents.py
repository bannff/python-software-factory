"""Agent Registry — unified persona source of truth
(bd:python-factory-d4roe.1, meta-architect verdict ``9d6a73fb`` Q2).

Stores ``AgentConfig`` Pydantic models (validated). ``load()`` seeds
the immutable built-in personas (``AGENTS_TYPED``) FIRST, then overlays
user-created personas from a polymorphic ``RegistryStore`` (disk YAML
locally; an AgentCore adapter slots in later behind the same Protocol).
Built-ins WIN on id collision. The legacy back-compat surface is
preserved: ``self.agents`` is a dict keyed by id; ``get`` returns the
typed model. Consumers wanting raw dicts call ``.model_dump()`` at the
boundary (mcp/tools.py, mcp/resources.py).
"""

from pathlib import Path
import logging

from ..runtime.registry_contracts import AgentConfig
from ..runtime.ports import RegistryStore
from .unified import merge_personas

logger = logging.getLogger(__name__)


__all__ = ["AgentConfig", "AgentRegistry"]


class AgentRegistry:
    """Registry for standalone agent configurations.

    ``store`` is the user-persona persistence port. When omitted it
    defaults to a ``DiskRegistryStore`` over ``config_dir`` — the same
    ``*.yaml`` / ``*.json`` directory the registry has always read.
    """

    def __init__(self, config_dir: Path | str, store: RegistryStore | None = None):
        self.config_dir = Path(config_dir)
        if store is None:
            from ..runtime.adapters.registry_store import DiskRegistryStore
            store = DiskRegistryStore(self.config_dir)
        self.store: RegistryStore = store
        self.agents: dict[str, AgentConfig] = {}

    async def load(self) -> None:
        """Seed built-in personas, then overlay the persisted store.

        Built-ins come from CODE (``AGENTS_TYPED``) and never depend on
        disk, so ``companion-x-default`` resolves identically whether or
        not the store is empty. User personas overlay on top; a user id
        that shadows a built-in is rejected (built-in wins).
        """
        from .defaults import AGENTS_TYPED
        merged = merge_personas(list(AGENTS_TYPED), self.store.load_personas())
        self.agents = {cfg.id: cfg for cfg in merged}

    def get(self, agent_id: str) -> AgentConfig | None:
        """Get agent configuration by ID."""
        return self.agents.get(agent_id)

    def build_agent(self, agent_id: str, **overrides):
        """Return a validated persona configuration for the runtime adapter."""
        config = self.get(agent_id)
        if config is None:
            raise ValueError(f"Agent '{agent_id}' not found")
        return AgentConfig.model_validate({**config.model_dump(), **overrides})

    def list_agents(self) -> list[dict]:
        """List all registered agents (dict shape for MCP surface)."""
        return [
            {"id": cfg.id, "name": cfg.name,
             "description": cfg.description, "model": cfg.model}
            for cfg in self.agents.values()
        ]
