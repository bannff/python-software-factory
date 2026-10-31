"""Hypothesis property tests for adapter-aware infrastructure resolution.

Properties verified:
- resolve_infra_from_bricks always returns a sorted list of strings
- resolve_infra_from_bricks output is deterministic (same input → same output)
- read_adapter_selections never crashes on arbitrary .env content
- Resolved services are always a subset of known infrastructure names
"""

from __future__ import annotations

import tempfile
from pathlib import Path

from hypothesis import given, settings
from hypothesis import strategies as st

from factory.blueprint.runtime.deploy.introspect import (
    read_adapter_selections,
    resolve_infra_from_bricks,
)
from factory.blueprint.runtime.deploy.templates import INFRA_ENV_VARS

KNOWN_SERVICES = set(INFRA_ENV_VARS.keys()) | {"neo4j", "redis", "keycloak"}

_adapter_key = st.text(
    min_size=1, max_size=20,
    alphabet=st.characters(whitelist_categories=("L", "N")),
)
_adapter_val = st.text(
    min_size=1, max_size=20,
    alphabet=st.characters(whitelist_categories=("L", "N")),
)


def _find_workspace_root() -> Path:
    path = Path(__file__).resolve()
    for parent in path.parents:
        if (parent / "workspace.toml").exists():
            return parent
    raise RuntimeError("Cannot find workspace root")


class TestAdapterInfraProperties:
    @settings(max_examples=50)
    @given(selections=st.dictionaries(_adapter_key, _adapter_val, max_size=10))
    def test_resolve_returns_sorted_strings(self, selections):
        d = tempfile.mkdtemp()
        result = resolve_infra_from_bricks(Path(d), list(selections), selections)
        assert result == sorted(result)
        assert all(isinstance(s, str) for s in result)

    @settings(max_examples=50)
    @given(selections=st.dictionaries(_adapter_key, _adapter_val, max_size=10))
    def test_resolve_is_deterministic(self, selections):
        d = tempfile.mkdtemp()
        components = list(selections)
        r1 = resolve_infra_from_bricks(Path(d), components, selections)
        r2 = resolve_infra_from_bricks(Path(d), components, selections)
        assert r1 == r2

    @settings(max_examples=50)
    @given(content=st.text(max_size=500))
    def test_read_adapter_never_crashes(self, content):
        d = tempfile.mkdtemp()
        (Path(d) / ".env").write_text(content)
        result = read_adapter_selections(Path(d))
        assert isinstance(result, dict)

    @settings(max_examples=50)
    @given(
        selections=st.dictionaries(
            st.sampled_from(["cache", "graph", "events", "auth"]),
            st.sampled_from(["redis", "neo4j", "memory", "keycloak"]),
        ),
    )
    def test_resolved_services_subset_of_known(self, selections):
        ws = _find_workspace_root()
        result = resolve_infra_from_bricks(ws, list(selections), selections)
        assert set(result) <= KNOWN_SERVICES
