"""Migration MCP server composition."""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from factory.mcp_utils.runtime.tool_catalog import ToolCatalog

from .mcp import bundle_preview_tool, execution, lifecycle, operational
from .runtime.adapters.receipt_store_sql import SqlReceiptStore
from .runtime.bundle_preview import BundlePreviewRuntime
from .runtime.bundle_ref import resolve_bundle_ref
from .runtime.preview import PreviewRuntime


def get_runtime() -> PreviewRuntime:
    raw_root = os.getenv("KIROCREW_IMPORT_ROOT", "").strip()
    db_path = os.getenv("MIGRATION_DB_PATH", "./.storage/migration.db")
    return PreviewRuntime(
        Path(raw_root).expanduser() if raw_root else None,
        SqlReceiptStore(db_path=db_path),
    )


def get_bundle_runtime() -> BundlePreviewRuntime:
    db_path = os.getenv("MIGRATION_DB_PATH", "./.storage/migration.db")
    return BundlePreviewRuntime(resolve_bundle_ref, SqlReceiptStore(db_path=db_path))


def create_tool_catalog(runtime: PreviewRuntime | None = None) -> Any:
    catalog = ToolCatalog("migration-module")
    active = runtime or get_runtime()
    operational.register(catalog, lambda: active)
    execution.register(catalog, lambda: active)
    lifecycle.register(catalog, lambda: active)
    bundle_preview_tool.register(catalog, get_bundle_runtime)
    return catalog


def create_mcp_server(runtime: PreviewRuntime | None = None) -> Any:
    return create_tool_catalog(runtime)


__all__ = ["create_mcp_server", "create_tool_catalog", "get_runtime"]
