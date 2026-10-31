"""FastMCP server for the dataset brick public surface."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from .mcp import (
    blueprints,
    can_intelligence,
    can_projection,
    can_terminal,
    definitions,
    deterministic,
    keystone_pipeline,
    operational,
    register_prompts,
    register_resources,
)
from .runtime.definition_codec import DEFAULT_DEFINITION_MAX_BYTES, require_max_size


def _surface(storage_root: Path | None) -> tuple[Path, int]:
    root = storage_root or Path(os.environ.get("DATASET_STORAGE_ROOT", ".dataset_store"))
    limit = require_max_size(int(os.environ.get(
        "DATASET_DEFINITION_ARTIFACT_MAX_BYTES", DEFAULT_DEFINITION_MAX_BYTES,
    )))
    return root, limit


def _register_tools(registry: Any, root: Path, max_definition_bytes: int) -> None:
    definitions.register(registry, root, max_definition_bytes)
    blueprints.register(registry, root)
    operational.register(registry, root)
    can_terminal.register(registry, root)
    can_intelligence.register(registry, root)
    can_projection.register(registry)
    deterministic.register(registry, root)
    keystone_pipeline.register(registry)


def create_tool_catalog(storage_root: Path | None = None) -> Any:
    """Create the transport-neutral Dataset tool catalog."""
    from factory.mcp_utils.runtime.tool_catalog import ToolCatalog

    root, limit = _surface(storage_root)
    catalog = ToolCatalog("dataset")
    _register_tools(catalog, root, limit)
    register_resources(catalog, root)
    register_prompts(catalog)
    return catalog


def create_mcp_server(storage_root: Path | None = None) -> Any:
    """Return the canonical framework-neutral catalog."""
    return create_tool_catalog(storage_root)