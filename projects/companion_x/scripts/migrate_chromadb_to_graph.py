"""One-shot ChromaDB -> graph migration (M7.7 Unified graph memory).

Moves every existing Memory (A-MEM/ChromaDB) and KB (Chroma) record into the
shared persistent-networkx graph store.

Gate A.5 AMEND fixes applied (compx-auditor `23de288c`):
  P0 - the memory half read the WRONG database. ``AMemStore()`` only
       defaults to ``./chroma_db`` when ``AMEM_STORAGE_PATH`` is unset; the
       owner's real ``.env`` sets ``AMEM_STORAGE_PATH=./chroma_memory``
       (2,517 real records, actively written by the live stack). This
       script now reads that env var explicitly rather than constructing
       ``AMemStore()`` with no args and silently getting the wrong store.
  P1 - the memory half's idempotency claim was false. ``GraphMemoryStore.
       store()`` always mints a fresh uuid4 and stamps ``now()`` -- re-
       running the migration would duplicate every record and scramble
       ``created_at``-based ordering. This script now writes memory nodes
       directly via the graph's ``add_entity``/``get_entity`` (a genuine
       upsert keyed on the record's OWN id -- confirmed idempotent, same
       primitive the KB half already correctly relies on) and preserves
       the source ``created_at``, calling ``GraphMemoryStore``'s own
       private ``_link_owner_and_chain``/``_link_similar`` afterward so
       the owner/chain/similarity edges still land exactly as ``store()``
       would produce them.
  P2 - removed the dead, misleading ``os.environ.setdefault("MEMORY_BACKEND",
       "amem")`` line; it never touched the real source knob (``AMEM_
       STORAGE_PATH``) and its comment masked the P0 above.

KB half was already correct (``KBGraphVectorStore.add`` upserts on the
document's own id) -- unchanged here.

Usage::

    uv run python projects/companion_x/scripts/migrate_chromadb_to_graph.py
    uv run python projects/companion_x/scripts/migrate_chromadb_to_graph.py --dry-run
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime
from typing import Any


def _memory_records() -> list[dict]:
    """Read every ChromaDB memory record from the REAL configured store.

    Unscoped enumeration is deliberate here (migration-only, outside the
    owner-scoped public port) -- every other memory read path stays scoped.
    """
    from factory.memory.runtime.adapters.amem import AMemStore
    from factory.memory.runtime.adapters.amem_helpers import unflatten_meta

    storage_path = os.environ.get("AMEM_STORAGE_PATH", "./chroma_db")
    store = AMemStore(storage_path=storage_path)
    if not store._collection.count():  # noqa: SLF001 -- migration-only raw read
        return []
    raw = store._collection.get()  # noqa: SLF001
    out = []
    for i, mid in enumerate(raw.get("ids", [])):
        meta = unflatten_meta(raw["metadatas"][i] if raw.get("metadatas") else {})
        meta["content"] = raw["documents"][i] if raw.get("documents") else ""
        meta["_id"] = mid
        out.append(meta)
    return out


def _migrate_memory(dry_run: bool) -> tuple[int, int]:
    from factory.graph.interface import Entity, GraphRuntime
    from factory.memory.runtime.adapters.graph_store import GraphMemoryStore

    records = _memory_records()
    if not records:
        return 0, 0
    if dry_run:
        return len(records), len(records)

    store = GraphMemoryStore()
    graph = GraphRuntime().get_graph("persistent_networkx")
    written = 0
    for meta in records:
        memory_id = meta["_id"]
        user_id = meta.get("user_id", "unknown")
        content = meta.get("content", "")
        created_at = meta.get("created_at") or datetime.now().isoformat()
        existing = graph.get_entity(memory_id)  # idempotent: same source id every re-run
        props: dict[str, Any] = {
            "user_id": user_id, "content": content,
            "memory_type": meta.get("memory_type", "short_term"),
            "category": meta.get("category", "custom"),
            "created_at": created_at, "relevance_score": 1.0,
        }
        extra = meta.get("extra") or {}
        for k, v in extra.items():
            if isinstance(v, (str, int, float, bool)):
                props[f"meta_{k}"] = v
        graph.add_entity(Entity(id=memory_id, type="memory", properties=props))
        if existing is None:  # only link owner/chain/similarity on first write
            store._link_owner_and_chain(user_id, memory_id)  # noqa: SLF001
            store._link_similar(memory_id, content, user_id)  # noqa: SLF001
        written += 1
    return len(records), written


def _migrate_kb(dry_run: bool) -> tuple[int, int]:
    from factory.kb.runtime.retrieval.chroma import ChromaVectorStore, ChromaConfig
    from factory.kb.runtime.retrieval.graph import KBGraphVectorStore
    from factory.kb.runtime.models import Document

    chroma_dir = os.environ.get("KB_CHROMA_DIR", "./chroma_data")
    source = ChromaVectorStore(ChromaConfig(persist_directory=chroma_dir))
    documents = source.list_documents(limit=10_000)
    if not documents:
        return 0, 0
    target = None if dry_run else KBGraphVectorStore()
    written = 0
    for doc in documents:
        if dry_run:
            written += 1
            continue
        target.add(Document(id=doc.id, content=doc.content, metadata=doc.metadata, source=doc.source))
        written += 1
    return len(documents), written


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true", help="Count records without writing")
    args = parser.parse_args()

    mem_found, mem_written = _migrate_memory(args.dry_run)
    kb_found, kb_written = _migrate_kb(args.dry_run)

    result = {
        "dry_run": args.dry_run,
        "memory": {
            "found": mem_found, "written": mem_written,
            "source_path": os.environ.get("AMEM_STORAGE_PATH", "./chroma_db"),
        },
        "kb": {"found": kb_found, "written": kb_written},
    }
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
