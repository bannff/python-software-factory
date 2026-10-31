"""Select MCP child servers eligible for gateway aggregation."""
from __future__ import annotations

import logging
from typing import Any

from .discovery import BrickDiscovery

logger = logging.getLogger("factory.mcp_server.core")
DEFAULT_EXCLUDE = {"foreman", "mcp_utils"}


def parse_brick_list(value: str) -> set[str]:
    """Parse a comma-separated brick environment variable."""
    if not value.strip():
        return set()
    return {brick.strip() for brick in value.split(",") if brick.strip()}


def resolve_brick_names(config: dict[str, Any]) -> list[str]:
    """Resolve configured loadable child servers, never gateway hosts."""
    discovery = BrickDiscovery()
    all_mcp_bricks = discovery.get_brick_names(mcp_only=True)
    available = discovery.get_brick_names(mcp_only=True, aggregation_only=True)
    include = parse_brick_list(config["include_bricks"])
    host_includes = sorted(include & (set(all_mcp_bricks) - set(available)))
    if host_includes:
        raise ValueError(
            "MCP_INCLUDE_BRICKS contains gateway host(s), which cannot be "
            f"loaded as child servers: {host_includes}"
        )
    exclude = parse_brick_list(config["exclude_bricks"]) or DEFAULT_EXCLUDE
    if include:
        available_set = set(available)
        dropped = sorted(available_set - include)
        stale = sorted(include - available_set)
        if dropped:
            logger.warning(
                "MCP_INCLUDE_BRICKS whitelist excludes available bricks: %s", dropped,
            )
        if stale:
            logger.warning("MCP_INCLUDE_BRICKS references unknown bricks: %s", stale)
        resolved = [brick for brick in available if brick in include]
    else:
        resolved = [brick for brick in available if brick not in exclude]
    logger.info("Resolved %d bricks: %s", len(resolved), sorted(resolved))
    return resolved
