"""Graph Registry — loads and manages graph/workflow configurations.

Stores ``RegistryConfig`` Pydantic models (``GraphConfig`` |
``WorkflowConfig``). YAML/JSON loaders validate via the
discriminated-union TypeAdapter so registration shape matters.
``self.graphs`` keyed by id; ``get`` returns the typed model.
"""

from pathlib import Path
from typing import Any
import json
import logging
import yaml

from pydantic import TypeAdapter

from ..runtime.registry_contracts import (
    EdgeConfig, GraphConfig, NodeConfig, NodeRef, RegistryConfig,
)

logger = logging.getLogger(__name__)


__all__ = [
    "EdgeConfig", "GraphConfig", "GraphRegistry",
    "NodeConfig", "NodeRef",
]

_GRAPH_ADAPTER: TypeAdapter[RegistryConfig] = TypeAdapter(RegistryConfig)


def _validate_graph(raw: Any) -> RegistryConfig:
    """Pydantic discriminated unions can't dispatch when ``kind`` is
    absent. Legacy dicts omit ``kind`` and mean graph; only workflow
    is explicit. Route manually here mirroring defaults._to_graph.
    """
    if isinstance(raw, dict) and raw.get("kind") == "workflow":
        return _GRAPH_ADAPTER.validate_python(raw)
    return GraphConfig.model_validate(raw)


class GraphRegistry:
    """Registry for graph/workflow configurations."""

    def __init__(self, config_dir: Path | str):
        self.config_dir = Path(config_dir)
        self.graphs: dict[str, RegistryConfig] = {}
        self._custom_node_types: dict[str, type] = {}

    async def load(self) -> None:
        """Load all graph configurations from directory."""
        if not self.config_dir.exists():
            return
        for config_file in self.config_dir.glob("*.yaml"):
            try:
                with open(config_file) as f:
                    raw = yaml.safe_load(f)
                if raw:
                    cfg = _validate_graph(raw)
                    self.graphs[cfg.id] = cfg
            except Exception as e:
                logger.warning("Failed to load %s: %s", config_file, e)
        for config_file in self.config_dir.glob("*.json"):
            try:
                with open(config_file) as f:
                    raw = json.load(f)
                if raw:
                    cfg = _validate_graph(raw)
                    self.graphs[cfg.id] = cfg
            except Exception as e:
                logger.warning("Failed to load %s: %s", config_file, e)

    def get(self, graph_id: str) -> RegistryConfig | None:
        """Get graph configuration by ID."""
        return self.graphs.get(graph_id)

    def register_node_type(self, name: str, cls: type) -> None:
        """Register a custom node type."""
        self._custom_node_types[name] = cls

    def get_node_type(self, name: str) -> type | None:
        """Get a registered custom node type."""
        return self._custom_node_types.get(name)

    def list_graphs(self) -> list[dict[str, Any]]:
        """List all registered graphs (MCP surface, dict shape)."""
        return [
            {"id": cfg.id, "name": cfg.name,
             "description": cfg.description,
             "node_count": len(getattr(cfg, "nodes", []) or []),
             "entry_points": list(getattr(cfg, "entry_points", []) or [])}
            for cfg in self.graphs.values()
        ]

    def list_graphs_with_schemas(self) -> list[dict[str, Any]]:
        """List all registered graphs with their structure."""
        return [
            {"id": cfg.id, "name": cfg.name,
             "description": cfg.description,
             "nodes": [{"id": n.id, "type": n.type}
                       for n in getattr(cfg, "nodes", []) or []],
             "edges": [{"source": e.source, "target": e.target}
                       for e in getattr(cfg, "edges", []) or []],
             "entry_points": list(getattr(cfg, "entry_points", []) or [])}
            for cfg in self.graphs.values()
        ]
