"""API-owned activation for owner-registered external MCP servers.

Bases compose: the API hands the connections runtime the gateway's
pseudo-brick mount seam and triggers one startup remount of every enabled
server so agents see external tools without an operator action.
"""
from __future__ import annotations

import inspect
import logging
from typing import Any

from factory.mcp_utils.interface import get_service

logger = logging.getLogger(__name__)


async def activate_connections(owner: Any) -> bool:
    loader = get_service("brick_tools")
    if callable(loader):
        loaded = loader("connections")
        if inspect.isawaitable(loaded):
            await loaded
    attach = get_service("connections_attach_gateway")
    remount = get_service("connections_remount_all")
    if not callable(attach) or not callable(remount):
        return False
    from factory.mcp_server.interface import get_aggregator
    from factory.mcp_server.runtime.external_mount import (
        register_external, unregister_external,
    )
    aggregator = get_aggregator()
    attach(
        lambda name, catalog: register_external(aggregator, name, catalog),
        lambda name: unregister_external(aggregator, name),
    )
    owner.submit(_remount(remount))
    return True


async def _remount(remount: Any) -> None:
    try:
        outcome = await remount()
    except Exception as exc:  # noqa: BLE001 - startup must not fail on one bad server
        logger.warning("connections: startup remount failed: %s", type(exc).__name__)
        return
    if outcome:
        logger.info("connections: mounted external MCP servers %s", outcome)


__all__ = ["activate_connections"]
