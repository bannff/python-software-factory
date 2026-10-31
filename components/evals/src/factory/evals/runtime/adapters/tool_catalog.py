"""Developer-owned static tool definitions for chaos simulation."""
from __future__ import annotations

from typing import Any

from pydantic import BaseModel

TOOL_NAMES = ("knowledge_search", "account_lookup", "order_status")


class _SearchResult(BaseModel):
    answer: str
    source: str


class _AccountResult(BaseModel):
    account_id: str
    status: str


class _OrderResult(BaseModel):
    order_id: str
    status: str


def register_catalog(simulator: Any, tool_names: tuple[str, ...]) -> list[Any]:
    """Register only selected static definitions and return SDK wrappers."""
    if "knowledge_search" in tool_names:
        @simulator.tool(output_schema=_SearchResult, name="knowledge_search", initial_state_description="Indexed facts")
        def knowledge_search(query: str) -> dict[str, str]:
            """Search the static knowledge catalog."""
            return {"answer": query, "source": "catalog"}

    if "account_lookup" in tool_names:
        @simulator.tool(output_schema=_AccountResult, name="account_lookup", initial_state_description="Account records")
        def account_lookup(account_id: str) -> dict[str, str]:
            """Retrieve a catalog account record."""
            return {"account_id": account_id, "status": "active"}

    if "order_status" in tool_names:
        @simulator.tool(output_schema=_OrderResult, name="order_status", initial_state_description="Order records")
        def order_status(order_id: str) -> dict[str, str]:
            """Retrieve a catalog order status."""
            return {"order_id": order_id, "status": "processing"}

    wrappers = [simulator.get_tool(name) for name in tool_names]
    if any(wrapper is None for wrapper in wrappers):
        raise RuntimeError("static tool catalog registration failed")
    return wrappers
