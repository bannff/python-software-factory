"""Built-in squad templates — one entry per target language.

A squad is a deployable team-of-agents (DATA). This is the "one file per
language" surface: add a `SquadConfig` here to ship a built-in squad. User
squads authored at runtime (via `agent_create_squad`) overlay these on disk.

The `team` topology references personas by `agent_id` (soft refs, resolved at
deploy time) and the `sandbox_profile` by name (soft ref into the sandbox
brick) — no cross-brick imports.
"""
from __future__ import annotations

from ..runtime.registry_contracts import SquadConfig

# Local toolbelt (LangChain framework tool names). File ops are root-confined
# to the workspace; shell covers cargo/rg/git/gh; web_search is in-container.
_CODE_TOOLBELT = {
    "tools": ["read_file", "write_file", "list_directory", "file_search",
              "shell", "web_search"],
}

RUST_SQUAD = SquadConfig(
    id="rust-squad",
    name="Rust Squad",
    description=(
        "Deployable team that clones, edits, builds and tests a Rust target "
        "repo inside a sandbox, then opens a PR. Phones home to Companion-X "
        "for memory/KB/graph."
    ),
    target_language="rust",
    sandbox_profile="rust-sdk",
    team={
        "kind": "graph",
        "id": "rust-team",
        "name": "Rust Team",
        "nodes": [
            {"id": "editor", "type": "agent", "agent_id": "developer",
             "description": "Edits the Rust codebase and runs cargo build/test."},
            {"id": "reviewer", "type": "agent", "agent_id": "developer",
             "description": "Reviews the diff, runs clippy, prepares the PR."},
        ],
        "edges": [{"source": "editor", "target": "reviewer"}],
        "entry_points": ["editor"],
    },
    toolbelt=_CODE_TOOLBELT,
    extra_deps=["langgraph"],
)

SQUADS_TYPED: list[SquadConfig] = [RUST_SQUAD]

__all__ = ["RUST_SQUAD", "SQUADS_TYPED"]
