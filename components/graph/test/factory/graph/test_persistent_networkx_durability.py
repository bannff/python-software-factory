"""Cross-process durability regression for local Graph snapshots."""
from __future__ import annotations

import multiprocessing
from pathlib import Path
from unittest.mock import patch

import pytest

from factory.graph.runtime.adapters.persistent_networkx import (
    PersistentNetworkXGraph,
)
from factory.graph.runtime.ports import Entity
from factory.storage.runtime.adapters.blob_local import LocalBlobStore


def _write_entity(root: str, entity_id: str, gate) -> None:
    store = LocalBlobStore(root_path=root)
    gate.wait()
    with patch(
        "factory.graph.runtime.adapters.persistent_networkx._get_blob_store",
        return_value=store,
    ):
        PersistentNetworkXGraph().add_entity(
            Entity(id=entity_id, type="Node", properties={}, labels=[]),
        )


def test_local_snapshot_lock_preserves_concurrent_process_updates(tmp_path: Path) -> None:
    if "fork" not in multiprocessing.get_all_start_methods():
        pytest.skip("cross-process lock test requires POSIX fork")
    root = str(tmp_path / "blobs")
    context = multiprocessing.get_context("fork")
    gate = context.Event()
    processes = [context.Process(
        target=_write_entity, args=(root, entity_id, gate),
    ) for entity_id in ("process-a", "process-b")]
    for process in processes:
        process.start()
    gate.set()
    for process in processes:
        process.join(timeout=10)
        assert process.exitcode == 0

    store = LocalBlobStore(root_path=root)
    with patch(
        "factory.graph.runtime.adapters.persistent_networkx._get_blob_store",
        return_value=store,
    ):
        graph = PersistentNetworkXGraph()

    assert graph.get_entity("process-a") is not None
    assert graph.get_entity("process-b") is not None
    assert (Path(root) / ".knowledge_graph_snapshot.json.lock").exists()
