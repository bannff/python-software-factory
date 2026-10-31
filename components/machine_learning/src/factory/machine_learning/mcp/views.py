"""Five ordered brick-declared views for the ML Observatory."""
from __future__ import annotations

from typing import Any
from factory.mcp_utils.interface import ToolResult, deterministic
from .views_dtos import EmptyInput, ViewsOutput
from .views_experiments import experiments_view
from .views_learning import learning_view
from .views_lineage import lineage_view
from .views_models_observatory import models_view
from .views_observatory import overview_view


def register(mcp: Any) -> None:
    """Register the exact ordered ML Observatory view surface."""

    @mcp.tool()
    @deterministic(input_model=EmptyInput, output_model=ViewsOutput)
    def ml_get_views() -> ToolResult[ViewsOutput]:
        """Return Overview, Experiments, Models, Learning, and Lineage."""
        return ViewsOutput(views=[overview_view(), experiments_view(), models_view(), learning_view(), lineage_view()])


__all__ = ["register"]
