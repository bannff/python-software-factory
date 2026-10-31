"""High-volume and concurrent Memory idempotency acceptance."""
from __future__ import annotations

import asyncio
from concurrent.futures import ThreadPoolExecutor
from threading import Event

from factory.memory.runtime.adapters.memory import InMemoryStore
from factory.memory.runtime.runtime import MemoryRuntime
from factory.memory.server import create_mcp_server
from factory.mcp_utils.interface import get_service, set_service
from factory.storage.runtime.adapters.doc_sqlite import SQLiteDocumentStore


def _storage(store: SQLiteDocumentStore):
    def invoke(name: str, **kwargs):
        if name == "storage_doc_get":
            document = store.get(kwargs["collection"], kwargs["doc_id"])
            return {"data": document.data} if document else {}
        if name == "storage_doc_create_or_match":
            result = store.create_or_match(
                kwargs["collection"], kwargs["doc_id"],
                kwargs["data"], kwargs["content_hash"],
            )
            return {
                "status": result.status,
                "existing_content_hash": result.existing_content_hash,
            }
        raise AssertionError(name)
    return invoke


def _tools(runtime: MemoryRuntime):
    catalog = create_mcp_server(runtime)
    return {tool.name: tool.fn for tool in asyncio.run(catalog.list_tools())}


def test_keyed_replay_is_independent_of_memory_count(tmp_path) -> None:
    runtime = MemoryRuntime(InMemoryStore())
    tools = _tools(runtime)
    previous = get_service("tool_invoker")
    set_service("tool_invoker", _storage(SQLiteDocumentStore(
        str(tmp_path / "ledger.db"),
    )))
    try:
        first = tools["memory_store"](
            content="durable reward", user_id="owner",
            idempotency_key="cycle-old",
        )
        for index in range(1_005):
            runtime.store("owner", f"ordinary-{index}")
        replay = tools["memory_store"](
            content="durable reward", user_id="owner",
            idempotency_key="cycle-old",
        )
        assert first.data.memory.id == replay.data.memory.id
        assert runtime.stats("owner").total_memories == 1_006
    finally:
        set_service("tool_invoker", previous)


class _SlowStore(InMemoryStore):
    def __init__(self, entered: Event, release: Event) -> None:
        super().__init__()
        self._entered, self._release = entered, release

    def store(self, *args, **kwargs):
        if kwargs.get("metadata", {}).get("idempotency_key") == "same-cycle":
            self._entered.set()
            assert self._release.wait(3)
        return super().store(*args, **kwargs)


def test_concurrent_equal_key_never_writes_twice(tmp_path) -> None:
    entered, release = Event(), Event()
    runtime = MemoryRuntime(_SlowStore(entered, release))
    tools = _tools(runtime)
    previous = get_service("tool_invoker")
    set_service("tool_invoker", _storage(SQLiteDocumentStore(
        str(tmp_path / "concurrent.db"),
    )))

    def write():
        return tools["memory_store"](
            content="one reward", user_id="owner",
            idempotency_key="same-cycle",
        )

    try:
        with ThreadPoolExecutor(max_workers=2) as pool:
            first_future = pool.submit(write)
            assert entered.wait(3)
            second = pool.submit(write).result(timeout=3)
            assert second.data.stored is False
            assert second.data.error == "memory idempotency in progress"
            release.set()
            first = first_future.result(timeout=3)
        replay = write()
        assert replay.data.memory.id == first.data.memory.id
        assert runtime.stats("owner").total_memories == 1
    finally:
        release.set()
        set_service("tool_invoker", previous)
