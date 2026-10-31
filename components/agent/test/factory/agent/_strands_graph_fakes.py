"""Graph-executor fakes for the multiagent-graph tests (same-dir helper
convention). The fake model replies ``node-<agent suffix>`` so node output
ordering is observable; the null client carries no capabilities."""
from __future__ import annotations

from typing import Any

from strands.models.model import Model

from factory.mcp_utils.runtime.scoped_capabilities import CapabilityScope


class GraphReplyModel(Model):
    """Text reply identifying the persona that produced it.

    The reply embeds the persona id the AGENT was built with (visible in
    the system prompt) so downstream ordering assertions can tell nodes
    apart without depending on upstream node text formatting.
    """

    def __init__(self) -> None:
        super().__init__()
        self.config: dict[str, Any] = {}

    def update_config(self, **model_config: Any) -> None:
        self.config.update(model_config)

    def get_config(self) -> Any:
        return self.config

    async def structured_output(
        self, output_model: Any, prompt: Any, **kwargs: Any,
    ) -> AsyncIterator[dict]:
        yield {}

    async def stream(
        self, messages: Any, tool_specs: Any = None, system_prompt: Any = None,
        **kwargs: Any,
    ) -> AsyncIterator[dict]:
        yield {"contentBlockDelta": {"delta": {"text": f"reply:{system_prompt}"}, "contentBlockIndex": 0}}
        yield {"contentBlockStop": {"contentBlockIndex": 0}}
        yield {"messageStop": {"stopReason": "end_turn"}}


class FakeGraphAgents:
    """Stand-in for ``StrandsAgentRuntime``: just the client seam."""

    def __init__(self) -> None:
        self._model_id = "fake"

    class _Client:
        scope = CapabilityScope.create("graph-test", set())

        async def list_capabilities(self) -> tuple[()]:
            return ()

    client = _Client()


def graph_request(
    nodes: list[tuple[str, str]], edges: list[tuple[str, str]], *,
    agent_id: str | None = None, max_steps: int = 64,
) -> Any:
    """Build a GraphRequest with persona-node pairs and edge pairs."""
    from factory.agent.runtime.runtime_contracts import (
        GraphEdge, GraphNode, GraphRequest, RuntimeInvocation,
    )

    entry = agent_id or (nodes[0][1] if nodes else "companion-x-default")
    return GraphRequest(
        invocation=RuntimeInvocation(
            invocation_id="graph-test-run", agent_id=entry, prompt="task",
            capability_scope_digest="scope", model_id="fake",
        ),
        nodes=tuple(GraphNode(node_id, persona) for node_id, persona in nodes),
        edges=tuple(GraphEdge(source, target) for source, target in edges),
        max_steps=max_steps,
    )


__all__ = ["FakeGraphAgents", "GraphReplyModel", "graph_request"]
