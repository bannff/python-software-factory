"""M5.5 trusted lesson-to-run-to-KB projection acceptance."""
from __future__ import annotations

import asyncio
import time
from types import SimpleNamespace
from unittest.mock import patch

from factory.events.runtime.runtime import EventsRuntime
from factory.events.server import create_mcp_server as create_events_server
from factory.graph.runtime.adapters.persistent_networkx import PersistentNetworkXGraph
from factory.graph.runtime.neighborhood import NeighborhoodRequest, encode_node_id
from factory.graph.runtime.runtime import GraphRuntime
from factory.graph.server import create_mcp_server as create_graph_server
from factory.kb.mcp.tools.projection import digest_content, emit_kb_projection
from factory.lessons.mcp.events import emit_lesson_event
from factory.mcp_server.runtime.aggregator import MCPAggregator
from factory.mcp_server.runtime.native_invoker import NativeEnvelopeInvoker
from factory.mcp_utils.interface import (
    get_service, reset_envelope, set_envelope, set_service,
)
from factory.storage.runtime.adapters.blob_local import LocalBlobStore
from factory.workflow.runtime.projection_events import emit_run_projection

TENANT, OWNER, RUN = "tenant", "owner", "run-1"


def test_lesson_run_kb_chain_survives_graph_reconstruction(tmp_path) -> None:
    store = LocalBlobStore(root_path=str(tmp_path / "blobs"))
    with patch(
        "factory.graph.runtime.adapters.persistent_networkx._get_blob_store",
        return_value=store,
    ):
        graph_runtime = GraphRuntime({"default_backend": "persistent_networkx"})
        graph = graph_runtime.get_graph("persistent_networkx")
        events = EventsRuntime(tmp_path / "events")
        aggregator = MCPAggregator()
        aggregator.set_available_bricks(["events", "graph"])
        aggregator._lazy._cache["events"] = create_events_server(events)
        aggregator._lazy._cache["graph"] = create_graph_server(graph_runtime)
        native = NativeEnvelopeInvoker(aggregator)
        previous_factory = get_service("tool_invoker_for_caller")
        previous_invoker = get_service("tool_invoker")
        set_service("tool_invoker_for_caller", native.for_caller)
        set_service("tool_invoker", aggregator.invoke_tool)
        token = set_envelope({
            "tenant_id": TENANT, "principal_id": OWNER, "run_id": RUN,
        })
        try:
            emit_kb_projection(
                "doc-1", content_digest=digest_content("private KB body"),
                references=[{
                    "kind": "workflow-run", "local_id": RUN,
                    "entity_type": "WorkflowRun", "relation_type": "about_run",
                }], tenant_id=TENANT, principal_id=OWNER,
            )
            emit_run_projection(
                tenant_id=TENANT, owner_id=OWNER, run_id=RUN,
                session_id="session-1", revision=1, status="succeeded",
                envelope={"tenant_id": TENANT, "principal_id": OWNER},
            )
            lesson = SimpleNamespace(
                tenant_id=TENANT, owner_id=OWNER,
                lesson_id="les_" + "a" * 32, identity_key="b" * 64,
                status=SimpleNamespace(value="accepted"),
                source=SimpleNamespace(value="outcome"),
                scope=SimpleNamespace(value="global"), scope_id=None,
                source_ref="kb:doc-1", superseded_ids=(), revision=1,
            )
            asyncio.run(emit_lesson_event(lesson, "lesson.accepted"))
            expected = {
                encode_node_id("lesson", TENANT, OWNER, lesson.lesson_id),
                encode_node_id("kb", TENANT, OWNER, "doc-1"),
                encode_node_id("workflow-run", TENANT, OWNER, RUN),
            }
            # The projection chain (events_publish -> graph write) crosses an
            # MCP invocation per hop and is polled, not awaited end-to-end.
            # 3s proved flaky on CI runners once the graph suite entered the
            # changed-brick selection; 30s keeps the poll semantics without
            # timing out on slow runners.
            deadline = time.monotonic() + 30
            expected_edges = {"derived_from", "learned_in", "about_run"}
            request = NeighborhoodRequest(
                (encode_node_id("lesson", TENANT, OWNER, lesson.lesson_id),),
                TENANT, OWNER, max_depth=2,
            )

            def _projected() -> bool:
                observed_now = graph.get_neighborhood(request)
                present_edges = {edge.type for edge in observed_now.relationships}
                return expected <= {e.id for e in observed_now.entities} \
                    and expected_edges <= present_edges

            while not _projected() and time.monotonic() < deadline:
                time.sleep(0.01)
            observed = graph.get_neighborhood(request)
            assert expected <= {entity.id for entity in observed.entities}
            edge_types = {edge.type for edge in observed.relationships}
            assert expected_edges <= edge_types
            restored = PersistentNetworkXGraph().get_neighborhood(request)
            assert restored == observed
            assert "private KB body" not in str(observed)
        finally:
            reset_envelope(token)
            set_service("tool_invoker_for_caller", previous_factory)
            set_service("tool_invoker", previous_invoker)
