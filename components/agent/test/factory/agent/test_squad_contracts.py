"""Tests for the SquadConfig data contract (deployable team-of-agents)."""
from __future__ import annotations

import pytest
from pydantic import ValidationError

from factory.agent.runtime.registry_contracts import (
    LocalToolbelt, PhoneHome, SquadConfig,
)


def _graph_team() -> dict:
    return {
        "kind": "graph", "id": "rust-team", "name": "Rust Team",
        "nodes": [
            {"id": "editor", "type": "agent", "agent_id": "rust-editor"},
            {"id": "reviewer", "type": "agent", "agent_id": "rust-reviewer"},
        ],
        "edges": [{"source": "editor", "target": "reviewer"}],
        "entry_points": ["editor"],
    }


def _rust_squad() -> dict:
    return {
        "id": "rust-squad", "name": "Rust Squad", "target_language": "rust",
        "sandbox_profile": "rust-sdk", "team": _graph_team(),
        "toolbelt": {"tools": ["shell", "file_read", "file_write", "edit", "grep"]},
        "model": "us.anthropic.claude-sonnet-4-6",
        "extra_deps": ["langgraph"],
    }


def test_valid_rust_squad_roundtrips():
    sq = SquadConfig(**_rust_squad())
    assert sq.kind == "squad"
    assert sq.sandbox_profile == "rust-sdk"
    assert sq.team.kind == "graph"
    assert sq.team.id == "rust-team"
    assert sq.toolbelt.tools[0] == "shell"


def test_default_phone_home_is_local_schema_compatible():
    sq = SquadConfig(**_rust_squad())
    # None is retained for local-only schema compatibility; remote prepare denies it.
    assert sq.phone_home.tool_allowlist is None
    assert sq.phone_home.mcp_url is None


def test_embeds_swarm_team():
    data = _rust_squad()
    data["team"] = {
        "kind": "swarm", "id": "sw", "name": "sw", "entry_point": "a",
        "agents": [
            {"id": "a", "model": "m", "system_prompt": "p"},
            {"id": "b", "model": "m", "system_prompt": "p"},
        ],
    }
    sq = SquadConfig(**data)
    assert sq.team.kind == "swarm"


@pytest.mark.parametrize("bad_id", ["Rust Squad", "UPPER", "has space", "-lead", ""])
def test_id_charset_enforced(bad_id):
    data = _rust_squad()
    data["id"] = bad_id
    with pytest.raises(ValidationError):
        SquadConfig(**data)


def test_sandbox_profile_required_nonempty():
    data = _rust_squad()
    data["sandbox_profile"] = "  "
    with pytest.raises(ValidationError):
        SquadConfig(**data)


def test_extra_keys_forbidden():
    data = _rust_squad()
    data["oops"] = True
    with pytest.raises(ValidationError):
        SquadConfig(**data)


def test_toolbelt_and_phonehome_defaults():
    data = _rust_squad()
    del data["toolbelt"]
    sq = SquadConfig(**data)
    assert sq.toolbelt.tools == []
    assert isinstance(sq.toolbelt, LocalToolbelt)
    assert isinstance(sq.phone_home, PhoneHome)


def test_narrowed_phone_home_allowlist():
    data = _rust_squad()
    data["phone_home"] = {"tool_allowlist": ["memory_store", "memory_retrieve"]}
    sq = SquadConfig(**data)
    assert sq.phone_home.tool_allowlist == ["memory_store", "memory_retrieve"]


def test_phone_home_rejects_empty_or_duplicate_allowlist():
    import pytest
    for allowlist in ([], ["memory_retrieve", "memory_retrieve"]):
        data = _rust_squad()
        data["phone_home"] = {"tool_allowlist": allowlist}
        with pytest.raises(ValueError, match="non-empty and unique"):
            SquadConfig(**data)
