"""Lazy standalone runner for MCP-enabled brick catalogs."""
from __future__ import annotations

from typing import Any, Callable


def make_lazy_runner(
    factory: Callable[..., Any],
) -> tuple[Callable[[], Any], Callable[[], None]]:
    """Create a lazy singleton getter and standalone runner."""
    instance: list[Any | None] = [None]

    def get_mcp_server() -> Any:
        if instance[0] is None:
            instance[0] = factory()
        return instance[0]

    def main() -> None:
        server = get_mcp_server()
        run = getattr(server, "run", None)
        if not callable(run):
            raise RuntimeError("neutral catalogs must be composed by the native MCP v2 server")
        run()

    return get_mcp_server, main
