"""Canonical Graph ToolResult contract tests for the sandbox graph store."""
from __future__ import annotations

from unittest.mock import patch

from factory.graph.mcp.core_models import (
    DeleteOutcomeData,
    EntityData,
    EntityLookupData,
    EntitySearchData,
)
from factory.mcp_utils.runtime.tool_result import fail, ok
from factory.sandbox.core import EnvironmentStatus
from factory.sandbox.runtime.adapters.graph_store import GraphSandboxStore
from factory.sandbox.runtime.models import EnvironmentInfo

_INVOKE = "factory.sandbox.runtime.adapters.graph_store._invoke"


def _environment() -> EnvironmentInfo:
    return EnvironmentInfo(
        env_id="env-1", status=EnvironmentStatus.RUNNING,
        instance_type="t3.micro", created_at="2026-01-01T00:00:00Z",
        metadata={"profile": "webgoat"},
    )


def _entity() -> EntityData:
    return EntityData(
        id="sandbox-env-env-1", type="SandboxEnvironment",
        properties={
            "env_id": "env-1", "status": "running",
            "instance_type": "t3.micro", "created_at": "2026-01-01T00:00:00Z",
            "metadata": '{"profile": "webgoat"}',
        },
    )


def test_load_and_list_unwrap_canonical_graph_data() -> None:
    entity = _entity()
    with patch(_INVOKE, side_effect=[
        ok(EntityLookupData(found=True, entity_id=entity.id, entity=entity)),
        ok(EntitySearchData(entities=[entity], count=1)),
    ]):
        store = GraphSandboxStore()
        loaded = store.load("env-1")
        listed = store.list_environments(status="running")

    assert loaded == _environment()
    assert listed == [_environment()]


def test_failed_graph_results_are_not_treated_as_success(caplog) -> None:
    with patch(_INVOKE, side_effect=[
        fail("write denied"), fail("read denied"), fail("search denied"),
        fail("delete denied"),
    ]):
        store = GraphSandboxStore()
        store.save(_environment())
        assert store.load("env-1") is None
        assert store.list_environments() == []
        assert store.delete("env-1") is False

    assert "write denied" in caplog.text


def test_delete_reads_typed_delete_outcome() -> None:
    with patch(_INVOKE, return_value=ok(DeleteOutcomeData(
        success=True, identifier="sandbox-env-env-1",
    ))):
        assert GraphSandboxStore().delete("env-1") is True
