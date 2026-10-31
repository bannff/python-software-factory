"""Hypothesis property tests for the unified persona registry merge
(bd:python-factory-d4roe.1, meta-architect verdict ``9d6a73fb`` Q2).

Pins the seed+overlay contract that unifies the persona source of
truth:

* built-in WINS on id collision (a user persona may not shadow a
  built-in id)
* user-ONLY personas surface in the merged result
* every built-in is always present (built-ins seeded from CODE, never
  depend on the store)
* round-trip: a user persona saved to a store and merged resolves back
  with identical fields
* ``DiskRegistryStore`` and ``InMemoryRegistryStore`` agree on the
  persona set for the same inputs
"""
from __future__ import annotations

from hypothesis import given, settings, strategies as st

from factory.agent.registry.unified import merge_personas
from factory.agent.runtime.adapters.registry_store import (
    DiskRegistryStore, InMemoryRegistryStore,
)
from factory.agent.runtime.registry_contracts import AgentConfig

# Contract-valid ids (lowercase alnum + -/_, first char alnum) — the
# AgentConfig.id validator (bd-67qvz) rejects anything else, so the
# strategy must only emit ids the contract accepts.
_id_strategy = st.from_regex(r"[a-z0-9][a-z0-9_-]{0,23}", fullmatch=True)


@st.composite
def _agent_config(draw, *, id_pool: st.SearchStrategy[str] = _id_strategy):
    return AgentConfig(
        id=draw(id_pool),
        name=draw(st.text(min_size=0, max_size=20)),
        model=draw(st.sampled_from(["m1", "m2", "us.anthropic.claude-sonnet-4-6"])),
        system_prompt=draw(st.text(min_size=0, max_size=40)),
    )


def _dedup_by_id(configs: list[AgentConfig]) -> list[AgentConfig]:
    seen: dict[str, AgentConfig] = {}
    for c in configs:
        seen[c.id] = c
    return list(seen.values())


@given(
    builtins=st.lists(_agent_config(), max_size=6),
    store=st.lists(_agent_config(), max_size=6),
)
@settings(max_examples=80, deadline=None)
def test_builtin_wins_and_user_only_surfaces(
    builtins: list[AgentConfig],
    store: list[AgentConfig],
) -> None:
    """For any built-in + store lists: built-ins always win on id
    collision, every built-in id is present, and user-only ids surface
    exactly once."""
    builtins = _dedup_by_id(builtins)
    store = _dedup_by_id(store)
    merged = merge_personas(builtins, store)
    by_id = {c.id: c for c in merged}

    builtin_ids = {b.id for b in builtins}
    # Every built-in present and unchanged (built-in instance wins).
    for b in builtins:
        assert by_id[b.id] is b
    # User-only ids surface; colliding user ids are dropped.
    for s in store:
        if s.id in builtin_ids:
            assert by_id[s.id] is not s  # built-in kept, not the user one
        else:
            assert by_id[s.id] is s
    # No duplicate ids in the merged list.
    assert len(merged) == len({c.id for c in merged})
    # Merged ids == union of both id sets.
    assert set(by_id) == builtin_ids | {s.id for s in store}


@given(store=st.lists(_agent_config(), max_size=6))
@settings(max_examples=60, deadline=None)
def test_disk_and_memory_stores_agree(
    tmp_path_factory,
    store: list[AgentConfig],
) -> None:
    """A ``DiskRegistryStore`` round-trips the same persona set an
    ``InMemoryRegistryStore`` holds for identical save inputs."""
    store = _dedup_by_id(store)
    tmp = tmp_path_factory.mktemp("personas")
    disk = DiskRegistryStore(tmp)
    mem = InMemoryRegistryStore()
    for cfg in store:
        disk.save_persona(cfg)
        mem.save_persona(cfg)

    disk_by_id = {c.id: c for c in disk.load_personas()}
    mem_by_id = {c.id: c for c in mem.load_personas()}

    assert set(disk_by_id) == set(mem_by_id) == {c.id for c in store}
    # Round-trip fidelity: every saved persona reloads field-identical.
    for cfg in store:
        assert disk_by_id[cfg.id] == cfg
        assert mem_by_id[cfg.id] == cfg


@given(store=st.lists(_agent_config(), min_size=1, max_size=5))
@settings(max_examples=40, deadline=None)
def test_disk_store_delete_removes_only_target(
    tmp_path_factory,
    store: list[AgentConfig],
) -> None:
    """``delete_persona`` removes exactly the targeted id; siblings
    remain. Deleting a missing id is a no-op returning ``False``."""
    store = _dedup_by_id(store)
    tmp = tmp_path_factory.mktemp("personas")
    disk = DiskRegistryStore(tmp)
    for cfg in store:
        disk.save_persona(cfg)

    target = store[0].id
    assert disk.delete_persona(target) is True
    remaining = {c.id for c in disk.load_personas()}
    assert target not in remaining
    assert remaining == {c.id for c in store} - {target}
    # Deleting again (now absent) is a clean no-op.
    assert disk.delete_persona(target) is False
