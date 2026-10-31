"""Property + stateful tests for the owner-scoped Crew store (M6.5 slice 3).

Covers: identifier/credential grammar, owner-scoped isolation, revision-fenced
CAS (stale-revision conflict, monotonic revisions), exclusive create, and the
non-dangling default/delete fence — asserted against BOTH the in-memory and
disk adapters so they share one contract.
"""
from __future__ import annotations

import tempfile
from pathlib import Path

import pytest
from hypothesis import given, settings, strategies as st
from hypothesis.stateful import (
    RuleBasedStateMachine, initialize, invariant, rule,
)

from factory.agent.runtime.adapters.crew_store_disk import DiskCrewStore
from factory.agent.runtime.adapters.crew_store_memory import InMemoryCrewStore
from factory.agent.runtime.crew_contracts import (
    CrewConfig, CrewConflictError, CrewExistsError, CrewNotFoundError,
    credential_clean,
)

_T, _O = "tenant-1", "owner-1"


def _crew(owner: str, crew_id: str, *, model: str = "", revision: int = 1) -> CrewConfig:
    return CrewConfig(
        tenant_id=_T, owner_id=owner, id=crew_id, name="n",
        persona_id="companion-x-default", project="/tmp/x", memory_scope="scope",
        model=model, revision=revision,
    )


# ---- grammar / credential-shape rejection ----

@given(bad=st.sampled_from(["Upper", "1_ok".upper(), "has space", "-lead", "a" * 65, "", "x/y"]))
def test_crew_id_grammar_rejects(bad: str) -> None:
    with pytest.raises(Exception):
        _crew(_O, bad)


@given(secret=st.sampled_from([
    "ghp_" + "a" * 30, "sk-" + "b" * 24, "xoxb-" + "1" * 12,
]))
def test_identifier_rejects_credential_shapes(secret: str) -> None:
    assert credential_clean(secret) is False


def test_valid_ids_are_credential_clean() -> None:
    for good in ("crew-a", "crew_1", "data0"):
        assert credential_clean(good)
        assert _crew(_O, good).id == good


# ---- explicit CAS / isolation / fence unit checks (both adapters) ----

@pytest.fixture(params=["memory", "disk"])
def store(request, tmp_path: Path):
    if request.param == "memory":
        return InMemoryCrewStore()
    return DiskCrewStore(tmp_path / "crews")


def test_owner_scoped_isolation(store) -> None:
    store.create_crew(_crew(_O, "c1"))
    assert store.get_crew(_T, "owner-2", "c1") is None
    assert store.list_crews(_T, "owner-2") == []
    with pytest.raises(CrewNotFoundError):
        store.update_crew(_crew("owner-2", "c1"), 1)
    with pytest.raises(CrewNotFoundError):
        store.delete_crew(_T, "owner-2", "c1", 1)


def test_exclusive_create(store) -> None:
    store.create_crew(_crew(_O, "c1"))
    with pytest.raises(CrewExistsError):
        store.create_crew(_crew(_O, "c1"))


def test_revision_fenced_update(store) -> None:
    store.create_crew(_crew(_O, "c1"))
    nxt = store.update_crew(_crew(_O, "c1", model="m"), 1)
    assert nxt.revision == 2
    with pytest.raises(CrewConflictError):
        store.update_crew(_crew(_O, "c1"), 1)  # stale


def test_default_delete_fence_no_dangle(store) -> None:
    store.create_crew(_crew(_O, "c1"))
    store.set_default(_T, _O, "c1", 1)
    assert store.get_default(_T, _O) == "c1"
    store.delete_crew(_T, _O, "c1", 1)
    assert store.get_default(_T, _O) is None  # cleared in same fenced op


def test_set_default_requires_existing_crew(store) -> None:
    with pytest.raises(CrewNotFoundError):
        store.set_default(_T, _O, "ghost", 1)


# ---- stateful machine: shadow-model parity + invariants ----

_ids = st.sampled_from([f"c-{c}" for c in "abc"])
_owners = st.sampled_from(["owner-1", "owner-2"])


class CrewStoreMachine(RuleBasedStateMachine):
    @initialize()
    def setup(self) -> None:
        self._dir = Path(tempfile.mkdtemp(prefix="crew-sm-"))
        self.store = DiskCrewStore(self._dir)
        self.model: dict[tuple[str, str], CrewConfig] = {}
        self.default: dict[str, str] = {}

    @rule(owner=_owners, crew_id=_ids)
    def create(self, owner: str, crew_id: str) -> None:
        if (owner, crew_id) in self.model:
            with pytest.raises(CrewExistsError):
                self.store.create_crew(_crew(owner, crew_id))
            return
        created = self.store.create_crew(_crew(owner, crew_id))
        assert created.revision == 1
        self.model[(owner, crew_id)] = created

    @rule(owner=_owners, crew_id=_ids)
    def update(self, owner: str, crew_id: str) -> None:
        current = self.model.get((owner, crew_id))
        if current is None:
            with pytest.raises(CrewNotFoundError):
                self.store.update_crew(_crew(owner, crew_id), 1)
            return
        nxt = self.store.update_crew(
            _crew(owner, crew_id, model="m"), current.revision,
        )
        assert nxt.revision == current.revision + 1
        self.model[(owner, crew_id)] = nxt

    @rule(owner=_owners, crew_id=_ids)
    def set_default(self, owner: str, crew_id: str) -> None:
        current = self.model.get((owner, crew_id))
        if current is None:
            with pytest.raises(CrewNotFoundError):
                self.store.set_default(_T, owner, crew_id, 1)
            return
        self.store.set_default(_T, owner, crew_id, current.revision)
        self.default[owner] = crew_id

    @rule(owner=_owners, crew_id=_ids)
    def delete(self, owner: str, crew_id: str) -> None:
        current = self.model.get((owner, crew_id))
        if current is None:
            with pytest.raises(CrewNotFoundError):
                self.store.delete_crew(_T, owner, crew_id, 1)
            return
        self.store.delete_crew(_T, owner, crew_id, current.revision)
        del self.model[(owner, crew_id)]
        if self.default.get(owner) == crew_id:
            del self.default[owner]

    @invariant()
    def parity_and_no_dangle(self) -> None:
        for owner in ("owner-1", "owner-2"):
            listed = {c.id: c for c in self.store.list_crews(_T, owner)}
            expected = {
                cid: cfg for (own, cid), cfg in self.model.items() if own == owner
            }
            assert listed == expected
            default = self.store.get_default(_T, owner)
            assert default == self.default.get(owner)
            if default is not None:  # default never dangles
                assert default in listed


TestCrewStoreStateful = CrewStoreMachine.TestCase
TestCrewStoreStateful.settings = settings(max_examples=60, deadline=None)
