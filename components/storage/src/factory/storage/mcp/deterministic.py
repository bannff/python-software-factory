"""Typed deterministic MCP tools for Storage."""
from __future__ import annotations

from typing import Callable, TYPE_CHECKING

from typing import Any
from factory.mcp_utils.interface import ToolResult, deterministic

from .contracts.base import EmptyInput
from .contracts.deterministic import CapabilitiesOutput, ConfigSchemaOutput, HealthOutput, StoreHealth

if TYPE_CHECKING:
    from ..runtime.runtime import StorageRuntime


def register(mcp: Any, get_runtime: Callable[[], "StorageRuntime"]) -> None:
    """Register deterministic tools with strict public contracts."""

    @mcp.tool()
    @deterministic(input_model=EmptyInput, output_model=CapabilitiesOutput)
    def get_capabilities() -> ToolResult[CapabilitiesOutput]:
        """Return machine-readable capabilities for storage brick."""
        from ..runtime.runtime import StorageRuntime
        return CapabilitiesOutput(name="storage", version="1.0.0", storage_types=["blob", "document", "sql", "graph"], backends=StorageRuntime.available_backends(), features=["blob_storage", "document_storage", "sql_storage", "graph_storage", "multi_backend", "health_checks"])

    @mcp.tool()
    @deterministic(input_model=EmptyInput, output_model=HealthOutput)
    def health_check() -> ToolResult[HealthOutput]:
        """Fast readiness probe for storage brick."""
        health = get_runtime().health_check()
        stores = {name: StoreHealth(healthy=item.healthy, backend=item.backend) for name, item in health.items()}
        return HealthOutput(healthy=all(item.healthy for item in stores.values()) if stores else True, stores=stores)

    @mcp.tool()
    @deterministic(input_model=EmptyInput, output_model=ConfigSchemaOutput)
    def describe_config_schema() -> ToolResult[ConfigSchemaOutput]:
        """Describe storage configuration schema."""
        return ConfigSchemaOutput(type="object", properties={"blob": {"type": "object", "properties": {"backend": {"type": "string", "enum": ["local", "s3"]}, "root_path": {"type": "string"}, "bucket": {"type": "string"}}}, "document": {"type": "object", "properties": {"backend": {"type": "string", "enum": ["tinydb", "mongodb"]}, "db_path": {"type": "string"}, "connection_string": {"type": "string"}}}, "sql": {"type": "object", "properties": {"backend": {"type": "string", "enum": ["sqlite", "postgres"]}, "db_path": {"type": "string"}, "connection_string": {"type": "string"}}}, "graph": {"type": "object", "properties": {"backend": {"type": "string", "enum": ["networkx", "neo4j"]}, "uri": {"type": "string"}, "auth_user": {"type": "string"}, "auth_password": {"type": "string"}}}})
