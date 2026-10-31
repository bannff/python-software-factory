"""Graph test fixtures — blob store isolation.

The persistent_networkx adapter is now the default backend. It persists
graph state via the storage brick's LocalBlobStore. Without isolation,
all tests would share a single .storage/blobs directory, causing:
- Cross-test state leakage (entity from test A visible in test B)
- Non-deterministic failures depending on test order
- Shared state across unrelated sessions in production

This conftest patches _get_blob_store at the MODULE level for the entire
test session, directing every PersistentNetworkXGraph instance to a
per-test-invocation temporary directory. Each test function gets a clean
slate automatically via pytest's function-scoped tmp_path.

Production keeps the real blob store (reached via service registry or
StorageRuntime fallback at .storage/blobs relative to the app working dir).
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from factory.storage.runtime.adapters.blob_local import LocalBlobStore


@pytest.fixture(autouse=True)
def _isolate_graph_blob_store(tmp_path: Path):
    """Patch the persistent graph's blob store to a per-test temp directory.

    autouse=True ensures EVERY test in this directory (and subdirectories)
    gets an isolated blob store, whether or not it explicitly requests it.
    This prevents cross-contamination when persistent_networkx is the default.
    """
    store = LocalBlobStore(root_path=str(tmp_path / "graph_blobs"))
    with patch(
        "factory.graph.runtime.adapters.persistent_networkx._get_blob_store",
        return_value=store,
    ):
        yield store
