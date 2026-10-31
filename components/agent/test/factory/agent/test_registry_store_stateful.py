"""Stateful Hypothesis property test for the user-persona store +
unified merge over arbitrary create / delete / recreate sequences
(bd:python-factory-d4roe.1 + .2, meta-architect verdict ``9d6a73fb``).

Models the create-on-a-whim lifecycle the ``agent_create_agent`` tool
drives, exercised at its write path (``DiskRegistryStore.save_persona``
== ``write_yaml_config`` net effect) + read path (``merge_personas``
over the disk store). A shadow ``dict`` tracks expected user personas;
invariants assert the unified merge stays in lock-step after EVERY
operation:

* every built-in is always present and byte-identical (built-ins win)
* the merged user-persona set == the shadow model exactly
* recreate overwrites (idempotent id, no duplicate rows)
* delete removes exactly the target; a missing-id delete is a no-op

Single-store-instance design: no per-example mutation of the
process-wide default store, so the test is independent + order-free.
"""
from __future__ import annotations

import tempfile
from pathlib import Path

from hypothesis import settings, strategies as st
from hypothesis.stateful import (
    RuleBasedStateMachine, initialize, invariant, rule,
)

from factory.agent.registry.defaults import AGENTS_TYPED
from factory.agent.registry.unified import merge_personas
from factory.agent.runtime.adapters.registry_store import DiskRegistryStore
from factory.agent.runtime.registry_contracts import AgentConfig

_BUILTIN_IDS = {b.id for b in AGENTS_TYPED}

# User ids drawn from a small pool so create/delete/recreate collide
# often (exercises overwrite + missing-id paths), filtered to never
# shadow a real built-in (the tool rejects those at the boundary).
_user_ids = st.sampled_from(
    [f"whim-{c}" for c in "abcde"]
).filter(lambda i: i not in _BUILTIN_IDS)
_names = st.text(min_size=0, max_size=20)


class RegistryStoreMachine(RuleBasedStateMachine):
    """Create / recreate / delete user personas; assert the unified
    merge mirrors a shadow model after every step."""

    @initialize()
    def setup(self) -> None:
        self._dir = Path(tempfile.mkdtemp(prefix="reg-sm-"))
        self.store = DiskRegistryStore(self._dir)
        self.model: dict[str, AgentConfig] = {}

    @rule(agent_id=_user_ids, name=_names)
    def create_or_update(self, agent_id: str, name: str) -> None:
        cfg = AgentConfig(
            id=agent_id, name=name, model="m1", system_prompt="p")
        self.store.save_persona(cfg)
        self.model[agent_id] = cfg

    @rule(agent_id=_user_ids)
    def delete(self, agent_id: str) -> None:
        expected = agent_id in self.model
        removed = self.store.delete_persona(agent_id)
        assert removed == expected
        self.model.pop(agent_id, None)

    @invariant()
    def merge_matches_model(self) -> None:
        merged = merge_personas(list(AGENTS_TYPED), self.store.load_personas())
        by_id = {c.id: c for c in merged}
        # Built-ins always present + byte-identical.
        for b in AGENTS_TYPED:
            assert by_id[b.id] == b
        # User personas mirror the shadow model exactly.
        user_ids = set(by_id) - _BUILTIN_IDS
        assert user_ids == set(self.model)
        for uid, cfg in self.model.items():
            assert by_id[uid] == cfg
        # No duplicate ids in the merged read path.
        assert len(merged) == len(by_id)


TestRegistryStoreStateful = RegistryStoreMachine.TestCase
TestRegistryStoreStateful.settings = settings(max_examples=50, deadline=None)
