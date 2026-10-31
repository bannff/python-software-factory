"""Workflow-driven recovery for dropped relationship-projection events."""
from __future__ import annotations

import hashlib
from unittest.mock import patch

import pytest

from factory.graph.runtime.adapters.persistent_networkx import PersistentNetworkXGraph
from factory.graph.runtime.neighborhood import NeighborhoodRequest, encode_node_id
from factory.graph.runtime.runtime import GraphRuntime
from factory.graph.server import create_mcp_server as create_graph_server
from factory.mcp_server.runtime.aggregator import MCPAggregator
from factory.mcp_server.runtime.native_invoker import NativeEnvelopeInvoker
from factory.mcp_utils.interface import (
    get_service, protected_canonical_json, set_service,
)
from factory.storage.runtime.adapters.blob_local import LocalBlobStore
from factory.workflow.runtime.projection_reconcile import reconcile_source_pages

TENANT, OWNER, RUN = "tenant", "owner", "run-dropped"
LESSON = "les_" + "a" * 32


def _item(subject_id: str, record: dict, revision: int = 1) -> dict:
    return {
        "subject_id": subject_id, "revision": revision,
        "payload_digest": hashlib.sha256(
            protected_canonical_json(record)
        ).hexdigest(),
        "record": record,
    }


def _loader(source: str, records: list[dict]):
    digest = hashlib.sha256(protected_canonical_json(records)).hexdigest()

    def load(cursor: str | None, limit: int) -> dict:
        start = int(cursor or "0")
        end = min(start + limit, len(records))
        return {
            "snapshot_id": f"{source}-snapshot-1",
            "snapshot_digest": digest,
            "records": tuple(records[start:end]),
            "next_cursor": str(end) if end < len(records) else None,
        }

    return load


def _record(source: str, kind: str, local_id: str, entity_type: str,
            references: list[dict] | None = None) -> dict:
    return {
        "source_system": source, "action": "upsert",
        "subject_kind": kind, "subject_local_id": local_id,
        "subject_type": entity_type,
        "source_digest": hashlib.sha256(local_id.encode()).hexdigest(),
        "references": references or [],
    }


def test_source_paging_recovers_dropped_events_and_survives_restart(tmp_path) -> None:
    private_body = "private KB body never projected"
    old_lesson = "les_" + "b" * 32
    lesson_records = [
        _item(old_lesson, _record("lessons", "lesson", old_lesson, "Lesson")),
        _item(LESSON, _record("lessons", "lesson", LESSON, "Lesson", [
            {"kind": "kb", "local_id": "doc-dropped",
             "entity_type": "KBDocument", "relation_type": "derived_from"},
            {"kind": "workflow-run", "local_id": RUN,
             "entity_type": "WorkflowRun", "relation_type": "learned_in"},
        ])),
    ]
    kb_record = _record("kb", "kb", "doc-dropped", "KBDocument")
    kb_record["source_digest"] = hashlib.sha256(private_body.encode()).hexdigest()
    run_record = _record("workflow", "workflow-run", RUN, "WorkflowRun", [{
        "kind": "session", "local_id": "session-dropped",
        "entity_type": "Session", "relation_type": "about_run",
    }])
    store = LocalBlobStore(root_path=str(tmp_path / "blobs"))
    with patch(
        "factory.graph.runtime.adapters.persistent_networkx._get_blob_store",
        return_value=store,
    ):
        runtime = GraphRuntime({"default_backend": "persistent_networkx"})
        graph = runtime.get_graph("persistent_networkx")
        assert graph.find_entities(limit=100) == []  # lifecycle dispatch was dropped
        aggregator = MCPAggregator()
        aggregator.set_available_bricks(["graph"])
        aggregator._lazy._cache["graph"] = create_graph_server(runtime)
        native = NativeEnvelopeInvoker(aggregator)
        previous = get_service("tool_invoker_for_caller")
        set_service("tool_invoker_for_caller", native.for_caller)
        try:
            receipts = reconcile_source_pages(
                tenant_id=TENANT, owner_id=OWNER, source_system="lessons",
                load_page=_loader("lessons", lesson_records), page_size=1,
            )
            assert [receipt.ordinal_start for receipt in receipts] == [0, 1]
            for source, records in (
                ("kb", [_item("doc-dropped", kb_record)]),
                ("workflow", [_item(RUN, run_record)]),
            ):
                reconcile_source_pages(
                    tenant_id=TENANT, owner_id=OWNER, source_system=source,
                    load_page=_loader(source, records), page_size=1,
                )
            request = NeighborhoodRequest(
                (encode_node_id("lesson", TENANT, OWNER, LESSON),),
                TENANT, OWNER, max_depth=2,
            )
            observed = graph.get_neighborhood(request)
            expected = {
                encode_node_id("lesson", TENANT, OWNER, LESSON),
                encode_node_id("kb", TENANT, OWNER, "doc-dropped"),
                encode_node_id("workflow-run", TENANT, OWNER, RUN),
                encode_node_id("session", TENANT, OWNER, "session-dropped"),
            }
            assert expected <= {entity.id for entity in observed.entities}
            assert {"derived_from", "learned_in", "about_run"} <= {
                edge.type for edge in observed.relationships
            }
            restored = PersistentNetworkXGraph().get_neighborhood(request)
            assert restored == observed
            assert private_body not in str(restored)
        finally:
            set_service("tool_invoker_for_caller", previous)


def test_source_page_rejects_foreign_source_before_graph_call() -> None:
    previous = get_service("tool_invoker_for_caller")
    set_service("tool_invoker_for_caller", lambda caller: lambda *args, **kwargs: {})
    foreign = _record("kb", "kb", "doc-foreign", "KBDocument")
    try:
        with pytest.raises(RuntimeError, match="foreign source"):
            reconcile_source_pages(
                tenant_id=TENANT, owner_id=OWNER, source_system="lessons",
                load_page=_loader("lessons", [_item("doc-foreign", foreign)]),
            )
    finally:
        set_service("tool_invoker_for_caller", previous)
