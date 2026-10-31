"""Operational MCP projection from immutable Dataset CAN artifacts to Graph."""
from __future__ import annotations

from typing import Any
from factory.mcp_utils.interface import ToolResult, operational

from .contracts.can import CanGraphProjectionOutput, ProjectCanGraphInput
from ..interface import dataset_project_can_graph


def register(mcp: Any) -> None:
    @mcp.tool(name="dataset_project_can_graph")
    @operational(input_model=ProjectCanGraphInput, output_model=CanGraphProjectionOutput)
    def project_can_graph(
        dataset_uri: str, graph_backend: str = "",
    ) -> ToolResult[CanGraphProjectionOutput]:
        """Project canonical CAN frames through named Graph MCP mutations."""
        return dataset_project_can_graph(dataset_uri, graph_backend)


__all__ = ["register"]
