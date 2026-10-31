"""Tests for the closure-observability `learning.applied` emit hook.

Producer: ``factory.memory.runtime.runtime.MemoryRuntime.retrieve``, delegated
through ``factory.memory.runtime.learning_emit.emit_learning_applied``.
Contract: bd python-factory-o7t8.

Covers:
- emit fires when a returned memory carries a `*-learnings` tag,
- emit does NOT fire when no memory carries a `*-learnings` tag,
- query > 256 chars is truncated and the hash is consistent,
- (Hypothesis) emit fires iff at least one tag ends with `-learnings`,
- emission failure is swallowed; retrieve still returns memories.
"""
from __future__ import annotations

from hashlib import sha256
from unittest.mock import MagicMock, patch

from hypothesis import given, settings, strategies as st

from factory.memory.runtime.adapters.memory import InMemoryStore
from factory.memory.runtime.runtime import MemoryRuntime


def _make_runtime() -> MemoryRuntime:
    return MemoryRuntime(store=InMemoryStore())


def _published(invoker: MagicMock) -> list[tuple[str, dict]]:
    """Extract (event_type, payload) for every events_publish call captured."""
    out: list[tuple[str, dict]] = []
    for call in invoker.call_args_list:
        args, kwargs = call
        if args and args[0] == "events_publish":
            out.append((kwargs["event_type"], kwargs["payload"]))
    return out


class TestLearningAppliedEmit:
    """`learning.applied` fires only when retrieved memories carry RL learnings."""

    def test_emits_when_returned_memory_has_learnings_tag(self):
        rt = _make_runtime()
        rt.store(
            user_id="u1",
            content="IDOR finding chain summary",
            metadata={
                "tags": ["IDOR", "sast-learnings", "run-1", "webgoat"],
                "run_id": "run-1",
            },
        )

        invoker = MagicMock()
        with patch(
            "factory.mcp_utils.registry._services", {"tool_invoker": invoker}
        ):
            results = rt.retrieve(user_id="u1", query="IDOR finding")

        assert len(results) == 1
        published = _published(invoker)
        assert len(published) == 1
        event_type, payload = published[0]
        assert event_type == "learning.applied"
        assert payload["retrieved_count"] == 1
        assert payload["retrieved_memory_ids"] == [results[0].id]
        assert payload["run_id"] == "run-1"
        assert payload["workflow_run_id"] == "run-1"
        assert payload["agent_id"] == "u1"  # falls back to user_id
        # idempotency_key shape: learning_applied:{run_id}:{agent_id}:{hash[:16]}
        assert payload["idempotency_key"].startswith("learning_applied:run-1:u1:")
        suffix = payload["idempotency_key"].split(":")[-1]
        assert len(suffix) == 16

    def test_does_not_emit_when_no_learnings_tag(self):
        rt = _make_runtime()
        rt.store(
            user_id="u1",
            content="just a regular note",
            metadata={"tags": ["IDOR", "run-1"], "run_id": "run-1"},
        )

        invoker = MagicMock()
        with patch(
            "factory.mcp_utils.registry._services", {"tool_invoker": invoker}
        ):
            results = rt.retrieve(user_id="u1", query="just a regular note")

        assert len(results) == 1  # retrieval still works
        assert _published(invoker) == []  # but no learning.applied event

    def test_query_longer_than_256_chars_is_truncated_and_hash_is_consistent(self):
        rt = _make_runtime()
        rt.store(
            user_id="u1",
            content="long query target",
            metadata={
                "tags": ["sast-learnings"],
                "run_id": "run-2",
            },
        )

        long_query = "x" * 500 + " long query target"
        truncated = long_query[:256]
        expected_hash = sha256(truncated.encode()).hexdigest()[:16]

        invoker = MagicMock()
        with patch(
            "factory.mcp_utils.registry._services", {"tool_invoker": invoker}
        ):
            rt.retrieve(user_id="u1", query=long_query, min_relevance=0.0)

        published = _published(invoker)
        assert len(published) == 1
        _, payload = published[0]
        assert payload["query"] == truncated
        assert len(payload["query"]) == 256
        assert payload["idempotency_key"].endswith(expected_hash)

    @settings(max_examples=30, deadline=None)
    @given(
        tags=st.lists(
            st.text(
                min_size=1,
                max_size=24,
                alphabet=st.characters(whitelist_categories=("L", "N", "P")),
            ),
            min_size=0,
            max_size=8,
        )
    )
    def test_emit_fires_iff_any_tag_ends_with_learnings(self, tags):
        """For random tag sets, emission iff at least one ends with `-learnings`."""
        rt = _make_runtime()
        rt.store(
            user_id="u1",
            content="hypothesis target",
            metadata={"tags": list(tags), "run_id": "run-h"},
        )

        invoker = MagicMock()
        with patch(
            "factory.mcp_utils.registry._services", {"tool_invoker": invoker}
        ):
            rt.retrieve(user_id="u1", query="hypothesis target")

        expected_emit = any(
            isinstance(t, str) and t.endswith("-learnings") for t in tags
        )
        published = _published(invoker)
        if expected_emit:
            assert len(published) == 1
            assert published[0][0] == "learning.applied"
        else:
            assert published == []

    def test_emission_failure_does_not_propagate(self):
        rt = _make_runtime()
        rt.store(
            user_id="u1",
            content="emit-failure target",
            metadata={
                "tags": ["dast-learnings"],
                "run_id": "run-3",
            },
        )

        invoker = MagicMock(side_effect=RuntimeError("boom"))
        with patch(
            "factory.mcp_utils.registry._services", {"tool_invoker": invoker}
        ):
            results = rt.retrieve(user_id="u1", query="emit-failure target")

        # Retrieve still returns its memories despite emit blowing up.
        assert len(results) == 1
        assert results[0].user_id == "u1"
