"""bd:python-factory-vs1vu — _store_learnings tags kwarg shape.

Pin the fix from meta-architect verdict ``2efd2a40`` Q9: tags ride
inside ``metadata={"tags": [...]}`` so they land in
``MemoryQuery.metadata.tags`` — the surface ``memory_retrieve(tags=...)``
(bd:python-factory-lin6p) reads from. The bug was latent since #550
where ``_store_learnings`` passed ``tags=[...]`` as a top-level kwarg;
``memory_store`` only accepts ``content,user_id,memory_type,category,
metadata,ttl_seconds`` so the call raised ``TypeError`` (or FastMCP
``ValidationError`` at the MCP boundary). The broad ``except`` block
in ``_store_learnings`` swallowed it, so memories were NEVER stored.

End-to-end loop closure pinned by
``test_store_learnings_recallable_via_tags_filter``.
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

from hypothesis import given, settings, strategies as st

from factory.games.runtime.game_pipeline import process_game_finished
from factory.memory.runtime.runtime import MemoryRuntime


def _payload(domain_class: str = "wine_pairing", run_id: str = "r-1") -> dict:
    """Game.finished payload with one finding submission."""
    return {
        "game_id": "g-vs1vu", "game_type": "scan", "winner": 1,
        "reward": {1: 1.0}, "move_count": 1,
        "move_history": [
            {"action": "submit_finding",
             "move": {"match": "vulnerability"}},
        ],
        "config": {"domain_class": domain_class, "run_id": run_id},
        "players": {1: "agent-alpha"},
    }


def _last_store_kwargs(invoker: MagicMock) -> dict:
    for call in reversed(invoker.call_args_list):
        if call[0] and call[0][0] == "memory_memory_store":
            return call[1]
    raise AssertionError("memory_memory_store was not invoked")


# Test 1 — kwarg shape lands in metadata, NOT top-level.
@patch("factory.games.runtime.game_pipeline._get_invoker")
def test_store_learnings_tags_land_in_metadata(mock_get):
    """The fix from verdict 2efd2a40 Q9: tags MUST ride inside
    ``metadata={"tags": [...]}``, not as a top-level kwarg. Asserts
    the canonical 4-tag dual-emit shape from bd:qer1z."""
    invoker = MagicMock(return_value={"ok": True})
    mock_get.return_value = invoker
    process_game_finished(_payload(domain_class="wine_pairing", run_id="r-1"))
    kwargs = _last_store_kwargs(invoker)
    assert "tags" not in kwargs, (
        "tags must NOT be a top-level kwarg — it raised TypeError pre-fix"
    )
    assert "metadata" in kwargs and isinstance(kwargs["metadata"], dict)
    tags = kwargs["metadata"].get("tags")
    assert tags == [
        "wine_pairing", "scan-learnings", "wine_pairing-learnings", "r-1",
    ]


# Test 2 — runtime acceptance: no TypeError when piped through real shape.
def test_store_learnings_no_typeerror_at_runtime():
    """End-to-end through ``MemoryRuntime.store(**kwargs)`` — proves the
    kwargs shape actually accepted by the runtime. Pre-fix, this raised
    ``TypeError: memory_store() got an unexpected keyword argument 'tags'``
    inside the broad except in ``_store_learnings``."""
    runtime = MemoryRuntime()

    def real_invoker(tool_name: str, **kwargs):
        if tool_name == "memory_memory_store":
            return runtime.store(**kwargs).model_dump()
        return {"ok": True}

    with patch(
        "factory.games.runtime.game_pipeline._get_invoker",
        return_value=real_invoker,
    ):
        result = process_game_finished(
            _payload(domain_class="wine_pairing", run_id="r-real"),
        )

    assert result["memory"].get("stored") is True, result["memory"]
    stored = runtime.list_all(user_id="kiro-agent")
    assert len(stored) == 1
    tags = stored[0].metadata.get("tags") or []
    assert "wine_pairing" in tags
    assert "scan-learnings" in tags
    assert "wine_pairing-learnings" in tags
    assert "r-real" in tags


# Test 3 — end-to-end loop closure: store then retrieve via tags filter.
def test_store_learnings_recallable_via_tags_filter():
    """The closure that proves the bug is dead: store via the pipeline,
    retrieve via ``memory_retrieve(tags=[f"{domain_class}-learnings"])``,
    confirm the stored memory is found. This is what
    ``LearningRecallPlugin`` (bd:zj026) will do at chat turn time."""
    runtime = MemoryRuntime()

    def real_invoker(tool_name: str, **kwargs):
        if tool_name == "memory_memory_store":
            return runtime.store(**kwargs).model_dump()
        return {"ok": True}

    with patch(
        "factory.games.runtime.game_pipeline._get_invoker",
        return_value=real_invoker,
    ):
        process_game_finished(
            _payload(domain_class="wine_pairing", run_id="r-recall"),
        )

    matches = runtime.retrieve(
        user_id="kiro-agent",
        query="Scan learnings wine_pairing run r-recall",
        min_relevance=0.0,  # rapidfuzz scores partial matches low; force inclusion.
        tags=["wine_pairing-learnings"],
    )
    assert len(matches) == 1
    assert matches[0].metadata.get("tags", []) == [
        "wine_pairing", "scan-learnings", "wine_pairing-learnings", "r-recall",
    ]
    other_domain = runtime.retrieve(
        user_id="kiro-agent",
        query="Scan learnings wine_pairing run r-recall",
        min_relevance=0.0,
        tags=["security_idor-learnings"],
    )
    assert other_domain == [], "tags filter must scope by domain"


# Test 4 — Hypothesis property: dual-emit invariant under random domains.
@given(
    domain_class=st.text(
        min_size=1, max_size=24,
        alphabet=st.characters(
            whitelist_categories=("L", "N"),
            whitelist_characters="_-",
        ),
    ),
    run_id=st.text(
        min_size=1, max_size=24,
        alphabet=st.characters(
            whitelist_categories=("L", "N"),
            whitelist_characters="_-",
        ),
    ),
)
@settings(max_examples=40, deadline=None)
def test_store_learnings_dual_emit_invariant(
    domain_class: str, run_id: str,
) -> None:
    """qer1z dual-emit: tag tuple is always
    ``[domain_class, "scan-learnings", f"{domain_class}-learnings", run_id]``
    AND lives inside ``metadata`` (vs1vu). One property covers both
    invariants because they collapse onto the same call site."""
    invoker = MagicMock(return_value={"ok": True})
    with patch(
        "factory.games.runtime.game_pipeline._get_invoker",
        return_value=invoker,
    ):
        process_game_finished(_payload(
            domain_class=domain_class, run_id=run_id,
        ))
    kwargs = _last_store_kwargs(invoker)
    assert "tags" not in kwargs  # vs1vu: not at top level.
    tags = kwargs["metadata"]["tags"]  # vs1vu: under metadata.
    assert tags == [
        domain_class, "scan-learnings",
        f"{domain_class}-learnings", run_id,
    ]
