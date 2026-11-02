from __future__ import annotations

import pytest

from factory.evals.mcp.views import _experiment_health
from factory.metrics.mcp.views import _item_list
from factory.ui.runtime.a2ui.components import COMPONENT_CATALOG
from factory.workflow.mcp.views import _runs_list


def test_item_list_schema_allows_empty_action() -> None:
    assert "empty_action" in COMPONENT_CATALOG["ItemList"].optional_props


@pytest.mark.parametrize("build", [_experiment_health, _item_list, _runs_list])
def test_empty_state_views_offer_a_prompt_action(build) -> None:
    props = build()["props"]
    assert isinstance(props["empty_action"], str) and props["empty_action"].strip()
    assert props["empty_message"], "an action without its message would have no context"
