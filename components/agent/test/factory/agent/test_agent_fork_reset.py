"""Row 33 (feature-map) — persona fork/reset, the "template fork-publish-
reset behavior" this row's own evidence flagged as absent.

Built-ins always win an id collision (``AgentRegistry.load`` docstring,
a deliberate existing invariant this feature does NOT change) — so a
fork always lands under a NEW id, never an in-place override. Reset
re-copies from the fork's recorded source, discarding local edits.
Provenance lives in a sidecar ``<id>.fork.json``, never inside the
strict ``AgentConfig`` (``extra="forbid"``) itself.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from factory.agent.authoring import AuthoringError, AuthoringManager
from factory.agent.registry.defaults import AGENTS_TYPED


@pytest.fixture
def manager(tmp_path: Path) -> AuthoringManager:
    (tmp_path / "agents").mkdir()
    return AuthoringManager(tmp_path)


def test_fork_provenance_round_trips(manager: AuthoringManager) -> None:
    assert manager.read_fork_provenance("agent", "no-such-id") is None
    manager.write_fork_provenance("agent", "my-fork", "companion-x-default")
    assert manager.read_fork_provenance("agent", "my-fork") == "companion-x-default"


def test_delete_yaml_config_clears_fork_provenance(manager: AuthoringManager) -> None:
    manager.write_yaml_config("agent", {
        "id": "my-fork", "name": "My Fork", "system_prompt": "hi",
    })
    manager.write_fork_provenance("agent", "my-fork", "companion-x-default")
    assert manager.read_fork_provenance("agent", "my-fork") == "companion-x-default"

    manager.delete_yaml_config("agent", "my-fork")
    assert manager.read_fork_provenance("agent", "my-fork") is None


def test_reset_provenance_survives_a_reset_rewrite(manager: AuthoringManager) -> None:
    """A reset re-writes the YAML (discarding edits) but must re-record
    the SAME provenance so a second reset still works."""
    manager.write_fork_provenance("agent", "my-fork", "companion-x-default")
    manager.write_yaml_config("agent", {
        "id": "my-fork", "name": "Edited name", "system_prompt": "edited",
    })
    assert manager.read_fork_provenance("agent", "my-fork") == "companion-x-default"

    # Simulate the reset tool's own re-write + re-record sequence.
    source = next(a for a in AGENTS_TYPED if a.id == "companion-x-default")
    manager.write_yaml_config("agent", {**source.model_dump(), "id": "my-fork"})
    manager.write_fork_provenance("agent", "my-fork", "companion-x-default")

    restored = manager.read_yaml_config("agent", "my-fork")
    assert restored["system_prompt"] == source.system_prompt
    assert manager.read_fork_provenance("agent", "my-fork") == "companion-x-default"


def test_provenance_sidecar_is_root_confined(manager: AuthoringManager) -> None:
    """Same path-escape guard every other authoring primitive gets."""
    with pytest.raises(AuthoringError):
        manager.write_fork_provenance("agent", "../../etc/passwd", "companion-x-default")
