"""Terminal orphan-reaper activation for the API lifespan."""
from __future__ import annotations

import asyncio
from typing import Any


async def _reap_forever() -> None:
    from factory.terminal.interface import get_runtime
    from .terminal_socket_owners import close_sockets_not_in
    from .terminal_ws_routes import prune_terminal_tickets
    while True:
        await asyncio.sleep(60)
        runtime = get_runtime()
        await runtime.registry.reap_orphans()
        active = runtime.active_session_ids()
        await close_sockets_not_in(active)
        prune_terminal_tickets(active)


async def activate_terminal_reaper(owner: Any) -> None:
    owner.submit(_reap_forever())


async def close_terminal_runtime() -> None:
    from factory.terminal.interface import get_runtime
    from .terminal_socket_owners import close_all_sockets
    from .terminal_ws_routes import prune_terminal_tickets
    runtime = get_runtime()
    await close_all_sockets()
    await runtime.close()
    prune_terminal_tickets(frozenset())


__all__ = ["activate_terminal_reaper", "close_terminal_runtime"]
