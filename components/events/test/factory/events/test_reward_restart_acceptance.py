"""M5.5 durable Memory/Evals reward restart acceptance."""
from __future__ import annotations

import asyncio
import gc

import pytest

chromadb = pytest.importorskip("chromadb")

from factory.evals.mcp.run_record_tools import register as register_run_record
from factory.events.runtime.learning_handlers.memory import handle_memory_learning
from factory.events.runtime.learning_handlers.reward import _bridge_reward_to_evals
from factory.events.runtime.models import Event
from factory.memory.runtime.adapters.amem import AMemStore
from factory.memory.runtime.runtime import MemoryRuntime
from factory.memory.server import create_mcp_server as create_memory_server
from factory.mcp_utils.interface import get_service, set_service
from factory.mcp_utils.runtime.tool_catalog import ToolCatalog
from factory.storage.runtime.adapters.doc_sqlite import SQLiteDocumentStore


def _release_chroma() -> None:
    gc.collect()
    from chromadb.api.shared_system_client import SharedSystemClient
    SharedSystemClient.clear_system_cache()


def _tool(catalog, name: str):
    return asyncio.run(catalog.get_tool(name)).fn


def _storage_invoker(store: SQLiteDocumentStore):
    def invoke(name: str, **kwargs):
        if name == "storage_doc_create_or_match":
            result = store.create_or_match(
                kwargs["collection"], kwargs["doc_id"],
                kwargs["data"], kwargs["content_hash"],
            )
            return {
                "status": result.status,
                "existing_content_hash": result.existing_content_hash,
            }
        if name == "storage_doc_get":
            document = store.get(kwargs["collection"], kwargs["doc_id"])
            return {"data": document.data} if document else {}
        raise AssertionError(name)
    return invoke


def _payload(identity: str) -> dict:
    return {
        "tenant_id": "tenant", "principal_id": "owner",
        "run_id": identity.rsplit(":", 1)[0],
        "workflow_run_id": identity.rsplit(":", 1)[0],
        "reward_identity": identity, "workflow_type": "dev-loop",
        "domain_class": "dev-loop", "score": 0.8,
        "precision": 0.8, "recall": 0.8, "reward_value": 80.0,
        "verdict": "rewarded", "profile_version": "v1",
    }


def _harness(memory_path, eval_path):
    runtime = MemoryRuntime(AMemStore(
        storage_path=str(memory_path), llm_complete=None,
    ))
    memory_store = _tool(create_memory_server(runtime), "memory_store")
    eval_store = SQLiteDocumentStore(str(eval_path))
    records = ToolCatalog("eval-records")
    register_run_record(records)
    eval_record = _tool(records, "evals_record_run")

    def invoke(name: str, **kwargs):
        if name == "events_query_events":
            return {"events": [], "total": 0}
        if name == "memory_memory_store":
            return memory_store(**kwargs)
        if name == "evals_record_run":
            return eval_record(**kwargs)
        raise AssertionError(name)

    return runtime, eval_store, invoke


def test_reward_memory_and_evals_dedupe_across_real_restart(tmp_path) -> None:
    memory_path, eval_path = tmp_path / "memory", tmp_path / "evals.db"
    previous_invoker = get_service("tool_invoker")
    previous_factory = get_service("tool_invoker_for_caller")
    set_service(
        "tool_invoker_for_caller",
        lambda caller: lambda *args, **kwargs: {"ok": True},
    )
    identity = "tenant:owner:loop-1:cycle-1:1:v1"
    try:
        _release_chroma()
        runtime, eval_store, invoke = _harness(memory_path, eval_path)
        set_service("tool_invoker", _storage_invoker(eval_store))
        event = Event(
            source="events.rewards", type="reward.computed",
            principal_id="owner", payload=_payload(identity),
        )
        first = handle_memory_learning(event, invoke)
        _bridge_reward_to_evals(invoke, event.payload, 80.0)
        first_id = first["memory_id"]
        assert len(runtime.list_all("owner", 100)) == 1
        assert eval_store.count("eval_results") == 1

        del runtime, eval_store, invoke
        _release_chroma()
        restarted, restarted_evals, restarted_invoke = _harness(
            memory_path, eval_path,
        )
        set_service("tool_invoker", _storage_invoker(restarted_evals))
        replay = handle_memory_learning(event, restarted_invoke)
        _bridge_reward_to_evals(restarted_invoke, event.payload, 80.0)
        assert replay["memory_id"] == first_id
        assert len(restarted.list_all("owner", 100)) == 1
        assert restarted_evals.count("eval_results") == 1

        second_payload = _payload("tenant:owner:loop-1:cycle-2:1:v1")
        second = handle_memory_learning(Event(
            source="events.rewards", type="reward.computed",
            principal_id="owner", payload=second_payload,
        ), restarted_invoke)
        _bridge_reward_to_evals(restarted_invoke, second_payload, 80.0)
        assert second["memory_id"] != first_id
        assert len(restarted.list_all("owner", 100)) == 2
        assert restarted_evals.count("eval_results") == 2
    finally:
        set_service("tool_invoker", previous_invoker)
        set_service("tool_invoker_for_caller", previous_factory)
        _release_chroma()
