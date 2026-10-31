"""Lifecycle + concurrency tests for the Agent Crew data seam (M6.5 slice 3).

Covers ambient identity, fixed model precedence with the non-empty guard,
Crew resolution through the existing persona resolver, concurrent same-revision
CAS yielding a single winner, cross-owner denial, and default/delete fence via
the lifecycle over the in-memory store.
"""
from __future__ import annotations

import threading

import pytest

from factory.agent.runtime.adapters.crew_store_memory import InMemoryCrewStore
from factory.agent.runtime.crew_contracts import (
    CrewConfig, CrewConflictError, CrewIdentityError, CrewModelUnresolvedError,
    CrewNotFoundError,
)
from factory.agent.runtime.crew_lifecycle import CrewLifecycle, _effective_model

_T, _O = "tenant-1", "owner-1"


def _seed(store: InMemoryCrewStore, owner: str, crew_id: str, *, model: str = "") -> CrewConfig:
    cfg = CrewConfig(
        tenant_id=_T, owner_id=owner, id=crew_id, name="n",
        persona_id="companion-x-default", project="/tmp/x",
        memory_scope="scope", model=model, revision=1,
    )
    return store.create_crew(cfg)


# ---- ambient identity ----

def test_identity_requires_envelope() -> None:
    with pytest.raises(CrewIdentityError):
        CrewLifecycle.identity(None)
    with pytest.raises(CrewIdentityError):
        CrewLifecycle.identity({"tenant_id": "t"})  # missing principal_id
    assert CrewLifecycle.identity(
        {"tenant_id": _T, "principal_id": _O},
    ) == (_T, _O)


# ---- model precedence ----

def test_model_precedence_order() -> None:
    assert _effective_model("s", "c", "p") == "s"
    assert _effective_model("", "c", "p") == "c"
    assert _effective_model("", "", "p") == "p"


def test_model_precedence_env_and_empty_guard(monkeypatch) -> None:
    monkeypatch.setenv("COMPANION_X_CHAT_MODEL", "env-model")
    assert _effective_model("", "", "") == "env-model"
    monkeypatch.delenv("COMPANION_X_CHAT_MODEL", raising=False)
    with pytest.raises(CrewModelUnresolvedError):
        _effective_model("", "", "")


# ---- resolution ----

def test_resolve_uses_crew_model_and_persona(monkeypatch) -> None:
    monkeypatch.delenv("COMPANION_X_CHAT_MODEL", raising=False)
    store = InMemoryCrewStore()
    _seed(store, _O, "c1", model="crew-model")
    lifecycle = CrewLifecycle(store)
    resolved = lifecycle.resolve(_T, _O, "c1")
    assert resolved.model_id == "crew-model"
    assert resolved.persona_id == "companion-x-default"
    assert resolved.memory_scope == "scope"
    # Session selection wins over the Crew model.
    assert lifecycle.resolve(_T, _O, "c1", session_model="sess").model_id == "sess"


def test_resolve_missing_crew(monkeypatch) -> None:
    monkeypatch.setenv("COMPANION_X_CHAT_MODEL", "env-model")
    lifecycle = CrewLifecycle(InMemoryCrewStore())
    with pytest.raises(CrewNotFoundError):
        lifecycle.resolve(_T, _O, "ghost")


# ---- cross-owner denial ----

def test_cross_owner_cannot_touch() -> None:
    store = InMemoryCrewStore()
    _seed(store, _O, "c1")
    lifecycle = CrewLifecycle(store)
    assert lifecycle.get(_T, "owner-2", "c1") is None
    assert lifecycle.list(_T, "owner-2") == []
    with pytest.raises(CrewNotFoundError):
        lifecycle.delete(_T, "owner-2", "c1", 1)


# ---- default / delete fence ----

def test_default_delete_fence() -> None:
    store = InMemoryCrewStore()
    _seed(store, _O, "c1")
    lifecycle = CrewLifecycle(store)
    lifecycle.set_default(_T, _O, "c1", 1)
    assert lifecycle.default_id(_T, _O) == "c1"
    lifecycle.delete(_T, _O, "c1", 1)
    assert lifecycle.default_id(_T, _O) is None


# ---- concurrent same-revision CAS: one winner ----

def test_concurrent_update_single_winner() -> None:
    store = InMemoryCrewStore()
    _seed(store, _O, "c1")
    lifecycle = CrewLifecycle(store)
    barrier = threading.Barrier(8)
    wins, conflicts = [], []

    def attempt(tag: int) -> None:
        cfg = CrewConfig(
            tenant_id=_T, owner_id=_O, id="c1", name=f"n{tag}",
            persona_id="companion-x-default", project="/tmp/x",
            memory_scope="scope", revision=1,
        )
        barrier.wait()
        try:
            store.update_crew(cfg, 1)
            wins.append(tag)
        except CrewConflictError:
            conflicts.append(tag)

    threads = [threading.Thread(target=attempt, args=(i,)) for i in range(8)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert len(wins) == 1
    assert len(conflicts) == 7
    assert store.get_crew(_T, _O, "c1").revision == 2
