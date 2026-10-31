"""Graph sink direct-writer context isolation tests."""
from __future__ import annotations

from types import SimpleNamespace

from factory.mcp_server.runtime._graph_sink_call import call_graph
from factory.mcp_utils.interface import (
    get_envelope, reset_envelope, set_envelope,
)


def test_parent_attempt_idempotency_is_not_applied_to_sink_writes() -> None:
    observed = {}

    def write(**kwargs):
        observed.update(get_envelope() or {})
        return kwargs

    outer = {
        "run_id": "wfr:v1:run",
        "attributes": {
            "workflow_attempt_id": "wfa:v1:attempt",
            "idempotency_key": "parent",
            "managed_graph.attempt_id": "wfa:v1:attempt",
        },
    }
    token = set_envelope(outer)
    try:
        result = call_graph(
            {"graph_add_entity": SimpleNamespace(fn=write)},
            "graph_add_entity", entity_id="invocation",
        )
        assert get_envelope() == outer
    finally:
        reset_envelope(token)

    assert result == {"entity_id": "invocation"}
    assert observed["run_id"] == "wfr:v1:run"
    assert observed["attributes"] == {
        "managed_graph.attempt_id": "wfa:v1:attempt",
    }
