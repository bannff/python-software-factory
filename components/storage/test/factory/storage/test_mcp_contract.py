"""Typed public-boundary regression tests for Storage contract tools."""
from __future__ import annotations

import asyncio

import pytest
from factory.mcp_utils.runtime.tool_catalog import ToolCatalog

from factory.mcp_utils.interface import ToolResult
from factory.storage.mcp import deterministic
from factory.storage.runtime.runtime import StorageRuntime, reset_runtime


class TestMCPContract:
    """Preserve contract behavior while asserting concrete typed envelopes."""

    @pytest.fixture(autouse=True)
    def reset(self) -> None:
        reset_runtime()

    @pytest.fixture
    def mcp(self) -> ToolCatalog:
        return ToolCatalog("test-storage")

    @pytest.fixture
    def runtime(self) -> StorageRuntime:
        return StorageRuntime()

    def _call(self, mcp: ToolCatalog, name: str, **kwargs):
        result = asyncio.run(mcp.get_tool(name)).fn(**kwargs)
        assert isinstance(result, ToolResult)
        assert result.ok is True
        return result.data

    def test_get_capabilities_returns_required_fields(self, mcp: ToolCatalog, runtime: StorageRuntime) -> None:
        deterministic.register(mcp, lambda: runtime)
        result = self._call(mcp, "get_capabilities")
        assert result.name == "storage"
        assert result.version
        assert isinstance(result.features, list)
        assert result.backends

    def test_get_capabilities_lists_storage_types(self, mcp: ToolCatalog, runtime: StorageRuntime) -> None:
        deterministic.register(mcp, lambda: runtime)
        result = self._call(mcp, "get_capabilities")
        assert {"blob", "document", "sql", "graph"} <= set(result.storage_types)

    def test_health_check_returns_healthy_status_without_stores(self, mcp: ToolCatalog, runtime: StorageRuntime) -> None:
        deterministic.register(mcp, lambda: runtime)
        result = self._call(mcp, "health_check")
        assert isinstance(result.healthy, bool)
        assert result.healthy is True
        assert result.stores == {}

    def test_health_check_with_active_stores(self, mcp: ToolCatalog, runtime: StorageRuntime, tmp_path) -> None:
        runtime.get_blob_store("local", root_path=str(tmp_path / "blobs"))
        deterministic.register(mcp, lambda: runtime)
        result = self._call(mcp, "health_check")
        assert result.healthy is True
        assert len(result.stores) == 1

    def test_describe_config_schema_returns_all_storage_types(self, mcp: ToolCatalog, runtime: StorageRuntime) -> None:
        deterministic.register(mcp, lambda: runtime)
        result = self._call(mcp, "describe_config_schema")
        assert result.type == "object"
        assert {"blob", "document", "sql", "graph"} <= set(result.properties)

    def test_describe_config_schema_lists_blob_backends(self, mcp: ToolCatalog, runtime: StorageRuntime) -> None:
        deterministic.register(mcp, lambda: runtime)
        result = self._call(mcp, "describe_config_schema")
        blob_properties = result.properties["blob"]["properties"]
        assert "backend" in blob_properties
        assert {"local", "s3"} <= set(blob_properties["backend"]["enum"])
