"""In-memory mock graph runtime for testing.

Provides deterministic graph execution without external dependencies.
"""

from __future__ import annotations

from typing import Any

from factory.agent.runtime.ports import GraphResult


class MemoryGraphRuntime:
    """In-memory implementation of GraphRuntime port."""

    def __init__(self) -> None:
        self._graphs: dict[str, dict[str, Any]] = {}
        self._builders: dict[int, dict[str, Any]] = {}
        self._builder_counter = 0

    def create_builder(self) -> dict[str, Any]:
        """Create a mock graph builder."""
        self._builder_counter += 1
        builder = {
            "id": self._builder_counter,
            "nodes": {},
            "edges": [],
            "entry_point": None,
        }
        self._builders[self._builder_counter] = builder
        return builder

    def add_node(self, builder: dict[str, Any], node: Any, node_id: str) -> None:
        """Add a node to the mock graph builder."""
        builder["nodes"][node_id] = node

    def add_edge(
        self, builder: dict[str, Any], source: str, target: str, condition: Any | None = None
    ) -> None:
        """Add an edge to the mock graph builder."""
        builder["edges"].append({"source": source, "target": target, "condition": condition})

    def set_entry_point(self, builder: dict[str, Any], node_id: str) -> None:
        """Set the entry point for the mock graph."""
        builder["entry_point"] = node_id

    def set_hook_providers(
        self, builder: dict[str, Any], hooks: list[Any]
    ) -> None:
        """No-op for memory adapter — hooks aren't invoked here."""
        builder["hooks"] = list(hooks or [])

    def build(self, builder: dict[str, Any]) -> dict[str, Any]:
        """Build the mock graph from the builder."""
        graph_id = f"graph_{builder['id']}"
        graph = {
            "id": graph_id,
            "nodes": builder["nodes"],
            "edges": builder["edges"],
            "entry_point": builder["entry_point"],
        }
        self._graphs[graph_id] = graph
        return graph

    async def invoke_async(
        self, graph: dict[str, Any], task: str, context: dict[str, Any] | None = None
    ) -> GraphResult:
        """Execute a mock graph - returns deterministic result."""
        node_ids = list(graph.get("nodes", {}).keys())
        return GraphResult(
            status="completed",
            execution_order=node_ids,
            results={"output": f"Graph executed for: {task[:30]}", "nodes": node_ids},
            execution_time=0.05,
        )


class MemoryToolLoader:
    """In-memory implementation of ToolLoader port."""

    def __init__(self) -> None:
        self._tools: dict[str, Any] = {}

    def register_tool(self, name: str, tool: Any) -> None:
        """Register a mock tool (test helper)."""
        self._tools[name] = tool

    def load_builtin_tools(self) -> list[Any]:
        """Load registered mock tools."""
        return list(self._tools.values())

    def load_tool(self, spec: str) -> Any | None:
        """Load a specific mock tool by name."""
        return self._tools.get(spec)
