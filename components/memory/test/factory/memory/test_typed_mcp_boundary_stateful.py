"""Stateful public FastMCP envelope properties for Memory filters."""
from __future__ import annotations

import asyncio
from typing import Any
from unittest.mock import MagicMock, patch

from hypothesis import settings, strategies as st
from hypothesis.stateful import RuleBasedStateMachine, invariant, rule, run_state_machine_as_test

from factory.memory.runtime.runtime import MemoryRuntime
from factory.memory.server import create_mcp_server


class MemoryBoundaryMachine(RuleBasedStateMachine):
    """Exercise storage, retrieval, and deletion through public tool functions."""

    def __init__(self) -> None:
        super().__init__()
        self._services = patch("factory.mcp_utils.registry._services", {"tool_invoker": MagicMock()})
        self._services.start()
        server = create_mcp_server(MemoryRuntime())
        self.tools = {tool.name: tool.fn for tool in asyncio.run(server.list_tools())}
        self.records: dict[str, tuple[set[str], str]] = {}
        self._store({"red"}, "one")
        self._store({"blue"}, "one")
        self._store({"red", "blue"}, "two")

    def teardown(self) -> None:
        self._services.stop()

    def _store(self, tags: set[str], run: str) -> None:
        result = self.tools["memory_store"](
            content="shared memory", user_id="u",
            metadata={"tags": sorted(tags), "run": run},
        )
        assert result.ok and result.data.stored and result.data.memory is not None
        self.records[result.data.memory.id] = tags, run

    def _ids(self, **kwargs: Any) -> set[str]:
        result = self.tools["memory_retrieve"](
            query="shared", user_id="u", min_relevance=0.0, limit=100, **kwargs,
        )
        assert result.ok
        return {memory.id for memory in result.data.memories}

    @rule(tags=st.sampled_from(({"red"}, {"blue"}, {"red", "blue"})),
          run=st.sampled_from(("one", "two")))
    def store(self, tags: set[str], run: str) -> None:
        self._store(tags, run)

    @rule()
    def delete_one(self) -> None:
        if self.records:
            memory_id = next(iter(self.records))
            result = self.tools["memory_delete"](memory_id=memory_id)
            assert result.ok and result.data.deleted
            del self.records[memory_id]

    @invariant()
    def retrieval_filters_remain_envelope_safe(self) -> None:
        all_ids = set(self.records)
        assert self._ids(tags=None) == all_ids
        assert self._ids(tags=[]) == set()
        assert self._ids(metadata=None) == all_ids
        assert self._ids(metadata={}) == all_ids
        for tag in ("red", "blue"):
            expected = {key for key, (tags, _) in self.records.items() if tag in tags}
            assert self._ids(tags=[tag]) == expected
        expected = {key for key, (_, run) in self.records.items() if run == "one"}
        assert self._ids(metadata={"run": "one"}) == expected
        expected = {
            key for key, (tags, run) in self.records.items()
            if "red" in tags and run == "one"
        }
        assert self._ids(tags=["red"], metadata={"run": "one"}) == expected


def test_public_typed_memory_boundary_state_machine() -> None:
    run_state_machine_as_test(MemoryBoundaryMachine, settings=settings(
        max_examples=12, stateful_step_count=8, deadline=None,
    ))
