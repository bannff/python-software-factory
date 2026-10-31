"""Catalog parity canary (bd:python-factory-3hkqx round 3).

Pins that every type in the BE ``COMPONENT_CATALOG`` (Python) has a
renderer entry in the canonical shared-renderer ``COMPONENT_MAP``
(TypeScript). Drift fails fast — a future BE catalog addition without
a matching FE renderer entry shows up as a failed catalog-parity test
instead of a silent yellow "Unknown component" box at runtime.

Meta-architect verdict ``cec79d55-7ff3-41c0-b583-781bc5d7d2b7`` Q6 T1.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from factory.ui.runtime.a2ui import COMPONENT_CATALOG


# Path resolution — repo root is 4 levels above this test file.
_REPO_ROOT = Path(__file__).resolve().parents[5]
_FE_MAP_PATH = (
    _REPO_ROOT
    / "frontends"
    / "shared-renderer"
    / "src"
    / "renderers"
    / "component-map.ts"
)


def _norm(s: str) -> str:
    return s.lower().replace("_", "")


def _extract_fe_map_keys(text: str) -> set[str]:
    """Pull property keys out of ``COMPONENT_MAP`` object literal.

    We parse the TS file as text — no node runtime in pytest. Match
    ``Identifier:`` and quoted-string keys before a colon. We're inside
    the ``export const COMPONENT_MAP = { ... }`` block.
    """
    block_match = re.search(
        r"export const COMPONENT_MAP[^=]*=\s*\{(?P<body>.*?)\}\s*;",
        text, flags=re.DOTALL,
    )
    assert block_match, "COMPONENT_MAP literal not found in component-map.ts"
    body = block_match.group("body")
    keys: set[str] = set()
    # Identifier-style keys: ``Card: CardRenderer,``
    keys.update(re.findall(r"^\s*([A-Za-z_][A-Za-z0-9_]*)\s*:", body, re.MULTILINE))
    # Quoted-string keys: ``"my-key": Renderer,``
    keys.update(re.findall(r"^\s*\"([^\"]+)\"\s*:", body, re.MULTILINE))
    keys.update(re.findall(r"^\s*'([^']+)'\s*:", body, re.MULTILINE))
    return keys


def test_fe_component_map_file_exists():
    assert _FE_MAP_PATH.exists(), f"canonical COMPONENT_MAP not at {_FE_MAP_PATH}"


def test_every_be_catalog_type_has_fe_renderer():
    """For every PascalCase key in ``COMPONENT_CATALOG``, the FE
    ``COMPONENT_MAP`` has SOME entry that normalizes to the same key.

    Symmetric with ``paint_canvas.py:_norm`` and FE
    ``component-map.ts:_norm`` — both lowercase and strip underscores."""
    fe_keys = _extract_fe_map_keys(_FE_MAP_PATH.read_text())
    fe_norm = {_norm(k) for k in fe_keys}
    missing: list[str] = []
    for be_type in COMPONENT_CATALOG.keys():
        if _norm(be_type) not in fe_norm:
            missing.append(be_type)
    assert not missing, (
        f"BE catalog types missing FE renderer entry: {missing}\n"
        f"FE map has {len(fe_keys)} keys (normalized: {len(fe_norm)})"
    )


@pytest.mark.parametrize("be_type", sorted(COMPONENT_CATALOG.keys()))
def test_each_catalog_type_resolves_in_fe_map(be_type):
    """Per-type assertion so test failures name the missing type."""
    fe_keys = _extract_fe_map_keys(_FE_MAP_PATH.read_text())
    fe_norm = {_norm(k) for k in fe_keys}
    assert _norm(be_type) in fe_norm, (
        f"{be_type!r} (normalized {_norm(be_type)!r}) has no FE renderer"
    )
