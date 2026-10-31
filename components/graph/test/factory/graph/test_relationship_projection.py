"""Trusted relationship projection and reconciliation semantics."""
from __future__ import annotations

import pytest
from hypothesis import given, strategies as st

from factory.graph.runtime.adapters.networkx_adapter import NetworkXGraph
from factory.graph.runtime.neighborhood import encode_node_id
from factory.graph.runtime.projection_reconcile import (
    ReconcileRecord, reconcile_projection,
)
from factory.graph.runtime.relationship_projection import (
    apply_projection, record_digest,
)

TENANT, OWNER = "tenant", "owner"


def _record(**changes) -> dict:
    value = {
        "source_system": "lessons", "action": "upsert",
        "subject_kind": "lesson", "subject_local_id": "lesson-1",
        "subject_type": "Lesson", "source_digest": "a" * 64,
        "references": [{
            "kind": "workflow-run", "local_id": "run-1",
            "entity_type": "WorkflowRun", "relation_type": "learned_in",
        }],
    }
    value.update(changes)
    return value


def _apply(graph: NetworkXGraph, record: dict, revision: int = 1):
    return apply_projection(
        graph, tenant_id=TENANT, owner_id=OWNER,
        subject_id=record["subject_local_id"], revision=revision,
        payload_digest=record_digest(record), record=record,
    )


def test_projection_is_idempotent_revision_fenced_and_tombstoned() -> None:
    graph = NetworkXGraph()
    assert _apply(graph, _record()).status == "created"
    assert _apply(graph, _record()).status == "matched"
    assert _apply(graph, _record(source_digest="b" * 64)).status == "conflict"
    assert _apply(graph, _record(), revision=0).status == "stale"
    assert _apply(graph, _record(source_digest="c" * 64), revision=2).status == "updated"
    subject = encode_node_id("lesson", TENANT, OWNER, "lesson-1")
    assert graph.get_entity(subject) is not None
    tombstone = _record(action="tombstone", references=[], source_digest="d" * 64)
    assert _apply(graph, tombstone, revision=3).status == "tombstoned"
    assert graph.get_entity(subject) is None


def test_invalid_relation_fails_before_any_mutation() -> None:
    graph = NetworkXGraph()
    record = _record(references=[{
        "kind": "workflow-run", "local_id": "run-1",
        "entity_type": "WorkflowRun", "relation_type": "forged",
    }])
    with pytest.raises(ValueError, match="unsupported"):
        _apply(graph, record)
    assert graph.health_check().node_count == 0


def _item(local_id: str, revision: int = 1) -> ReconcileRecord:
    record = _record(subject_local_id=local_id, references=[])
    return ReconcileRecord(
        subject_id=local_id, revision=revision,
        payload_digest=record_digest(record), record=record,
    )


def test_reconciliation_cursor_is_monotonic_and_exact_replay_dedupes() -> None:
    graph = NetworkXGraph()
    kwargs = {
        "tenant_id": TENANT, "owner_id": OWNER, "source_system": "lessons",
        "snapshot_id": "snapshot", "snapshot_digest": "e" * 64,
        "ordinal_start": 0, "cursor": None, "next_cursor": "page-2",
        "page_digest": "f" * 64, "records": (_item("lesson-1"),),
    }
    first = reconcile_projection(graph, **kwargs)
    assert first.applied == 1 and first.last_ordinal == 0
    replay = reconcile_projection(graph, **kwargs)
    assert replay.duplicates == 1 and replay.applied == 0
    second = reconcile_projection(
        graph, **{**kwargs, "ordinal_start": 1, "cursor": "page-2",
                  "next_cursor": None, "page_digest": "1" * 64,
                  "records": (_item("lesson-2"),)},
    )
    assert second.applied == 1 and second.last_ordinal == 1
    with pytest.raises(ValueError, match="monotonic"):
        reconcile_projection(
            graph, **{**kwargs, "ordinal_start": 3, "cursor": None,
                      "next_cursor": None, "page_digest": "2" * 64,
                      "records": (_item("lesson-3"),)},
        )


@given(st.lists(st.from_regex(
    r"[a-z0-9][a-z0-9-]{0,11}", fullmatch=True,
), min_size=1, max_size=12, unique=True))
def test_reconciliation_pages_advance_once_and_replay_as_duplicates(ids: list[str]) -> None:
    graph = NetworkXGraph()
    cursor = None
    for ordinal, local_id in enumerate(ids):
        item = _item(local_id)
        kwargs = {
            "tenant_id": TENANT, "owner_id": OWNER,
            "source_system": "lessons", "snapshot_id": "property-snapshot",
            "snapshot_digest": "9" * 64, "ordinal_start": ordinal,
            "cursor": cursor, "next_cursor": f"cursor-{ordinal}",
            "page_digest": f"{ordinal:064x}", "records": (item,),
        }
        first = reconcile_projection(graph, **kwargs)
        replay = reconcile_projection(graph, **kwargs)
        assert first.last_ordinal == ordinal and first.applied == 1
        assert replay.last_ordinal == ordinal and replay.duplicates == 1
        cursor = f"cursor-{ordinal}"
