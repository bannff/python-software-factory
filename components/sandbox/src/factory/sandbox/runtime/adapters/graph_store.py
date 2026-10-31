"""Graph-backed sandbox store via MCP tool invoker.

Persists SandboxEnvironment entities to Neo4j through the graph
brick's MCP tools. Uses the service registry pattern — no direct
graph brick imports, no Neo4j driver usage.

The metadata dict is JSON-serialized since Neo4j properties must
be primitives.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from factory.mcp_utils.interface import normalize_correlation

from ...core import EnvironmentStatus
from ..models import EnvironmentInfo

logger = logging.getLogger(__name__)

_ENTITY_TYPE = "SandboxEnvironment"
_ID_PREFIX = "sandbox-env-"


def _get_invoker():
    """Get the MCP tool invoker from the service registry.

    Returns None quickly if unavailable — never blocks.
    """
    try:
        from factory.mcp_utils.interface import get_service
        invoker = get_service("tool_invoker")
        if invoker is not None:
            return invoker
    except Exception:
        pass
    return None


def _invoke(tool_name: str, **kwargs: Any) -> Any:
    """Invoke a graph brick tool via the service registry."""
    invoker = _get_invoker()
    if invoker is None:
        raise RuntimeError("No tool invoker available for graph store")
    return invoker(tool_name, **kwargs)


def _entity_id(env_id: str) -> str:
    """Build the graph entity ID for a sandbox environment."""
    return f"{_ID_PREFIX}{env_id}"


def _serialize_props(env: EnvironmentInfo) -> dict[str, Any]:
    """Convert EnvironmentInfo to Neo4j-safe properties dict."""
    metadata = env.metadata if isinstance(env.metadata, dict) else {}
    props: dict[str, Any] = {
        "env_id": env.env_id,
        "status": env.status.value,
        "instance_type": env.instance_type,
        "created_at": env.created_at,
        "metadata": json.dumps(metadata),
    }
    for key, value in normalize_correlation(metadata, {"env_id": env.env_id, "entity_id": _entity_id(env.env_id)}).items():
        props.setdefault(key, value)
    if env.public_ip is not None:
        props["public_ip"] = env.public_ip
    if env.private_ip is not None:
        props["private_ip"] = env.private_ip
    return props


def _deserialize_env(entity: dict[str, Any]) -> EnvironmentInfo:
    """Reconstruct an EnvironmentInfo from graph entity properties."""
    props = entity.get("properties", entity)
    metadata = json.loads(props.get("metadata", "{}"))
    status_str = props.get("status", "unknown")
    try:
        status = EnvironmentStatus(status_str)
    except ValueError:
        status = EnvironmentStatus.UNKNOWN
    return EnvironmentInfo(
        env_id=props.get("env_id", ""),
        status=status,
        instance_type=props.get("instance_type", ""),
        created_at=props.get("created_at", ""),
        public_ip=props.get("public_ip"),
        private_ip=props.get("private_ip"),
        metadata=metadata,
    )


class GraphSandboxStore:
    """Persist sandbox environments to Neo4j via graph brick MCP tools."""

    def save(self, env: EnvironmentInfo) -> None:
        """Save or update a sandbox environment (MERGE semantics)."""
        try:
            result = _invoke(
                "graph_graph_add_entity",
                entity_id=_entity_id(env.env_id),
                entity_type=_ENTITY_TYPE,
                properties=_serialize_props(env),
            )
            if not result or not result.ok or result.data is None:
                logger.error("Failed to save env %s: %s", env.env_id,
                             getattr(result, "error", "missing graph result"))
        except Exception as e:
            logger.error("Failed to save env %s: %s", env.env_id, e)

    def load(self, env_id: str) -> EnvironmentInfo | None:
        """Load a sandbox environment by ID."""
        try:
            result = _invoke(
                "graph_graph_get_entity",
                entity_id=_entity_id(env_id),
            )
            if not result or not result.ok or result.data is None:
                return None
            entity = result.data.entity
            return _deserialize_env(entity.properties) if result.data.found and entity else None
        except Exception as e:
            logger.error("Failed to load env %s: %s", env_id, e)
            return None

    def list_environments(
        self, status: str | None = None,
    ) -> list[EnvironmentInfo]:
        """List sandbox environments, optionally filtered by status."""
        try:
            result = _invoke(
                "graph_graph_find_entities",
                entity_type=_ENTITY_TYPE,
            )
            if not result or not result.ok or result.data is None:
                return []
            envs = [_deserialize_env(entity.properties) for entity in result.data.entities]
            if status:
                envs = [e for e in envs if e.status.value == status]
            return envs
        except Exception as e:
            logger.error("Failed to list environments: %s", e)
            return []

    def delete(self, env_id: str) -> bool:
        """Delete a sandbox environment from the graph."""
        try:
            result = _invoke(
                "graph_graph_delete_entity",
                entity_id=_entity_id(env_id),
            )
            return bool(result and result.ok and result.data is not None
                        and result.data.success)
        except Exception as e:
            logger.error("Failed to delete env %s: %s", env_id, e)
            return False

    def health_check(self) -> dict[str, Any]:
        """Check graph brick connectivity."""
        try:
            result = _invoke("graph_graph_health_check")
            data = getattr(result, "data", None)
            return {"healthy": bool(result and result.ok and data and data.healthy),
                    "backend": "graph", "node_count": 0}
        except Exception as e:
            return {"healthy": False, "backend": "graph", "message": str(e)}
