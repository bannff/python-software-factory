"""Hypothesis round-trip property for the ``agent_create_agent`` tool
(bd:python-factory-d4roe.2, meta-architect verdict ``9d6a73fb`` Q4).

Pins the create → resolve → recreate-idempotent → delete cycle at the
unified read path the tool wires (``write_yaml_config`` to write +
``merge_personas`` over the disk store to read). Split from
``test_agent_create_agent_tool.py`` to keep both files under the
200-LOC tenet.
"""
from __future__ import annotations

from hypothesis import given, settings, strategies as st

from factory.agent.authoring import AuthoringManager
from factory.agent.registry.unified import merge_personas
from factory.agent.runtime.adapters.registry_store import DiskRegistryStore
from factory.agent.runtime.registry_contracts import AgentConfig

# Contract-valid id matching AgentConfig.id + authoring ``_ID_RE``
# (both now ``[a-z0-9][a-z0-9_-]{0,127}``, lowercase — bd-67qvz).
_id_strategy = st.from_regex(r"[a-z0-9][a-z0-9_-]{0,23}", fullmatch=True)


@given(
    agent_id=_id_strategy,
    name=st.text(min_size=0, max_size=20),
    prompt=st.text(min_size=0, max_size=40),
)
@settings(max_examples=40, deadline=None)
def test_create_resolve_recreate_delete_round_trip(
    tmp_path_factory, agent_id: str, name: str, prompt: str,
) -> None:
    """Round-trip idempotency at the unified read path: write a persona
    via the authoring manager, prove it resolves through the unified
    merge, re-create the same id idempotently, then delete it cleanly.

    Exercises the SAME write path (``write_yaml_config``) + read path
    (``merge_personas`` over the disk store) the tool wires, without
    per-example global-store mutation.
    """
    from factory.agent.registry.defaults import AGENTS_TYPED

    # Skip ids that collide with a real built-in — the tool rejects those
    # at the boundary; this property covers user-only ids.
    builtin_ids = {b.id for b in AGENTS_TYPED}
    if agent_id in builtin_ids:
        return

    config_root = tmp_path_factory.mktemp("cfg")
    (config_root / "agents").mkdir()
    manager = AuthoringManager(config_root)
    store = DiskRegistryStore(config_root / "agents")

    config = {
        "id": agent_id, "name": name,
        "model": "us.anthropic.claude-sonnet-4-5-20250929-v1:0",
        "system_prompt": prompt,
    }

    # create → resolves through the unified merge
    res = manager.write_yaml_config("agent", config)
    assert res["ok"] is True
    merged = {
        c.id: c
        for c in merge_personas(list(AGENTS_TYPED), store.load_personas())
    }
    assert agent_id in merged
    assert merged[agent_id] == AgentConfig.model_validate(config)

    # recreate same id is idempotent — still exactly one entry, updated
    config["name"] = name + "-v2"
    manager.write_yaml_config("agent", config)
    reloaded = store.load_personas()
    assert sum(1 for c in reloaded if c.id == agent_id) == 1
    merged2 = {
        c.id: c for c in merge_personas(list(AGENTS_TYPED), reloaded)
    }
    assert merged2[agent_id].name == name + "-v2"

    # delete works — id no longer resolves
    deleted = manager.delete_yaml_config("agent", agent_id)
    assert deleted["ok"] is True
    after = {
        c.id
        for c in merge_personas(list(AGENTS_TYPED), store.load_personas())
    }
    assert agent_id not in after
