"""Property tests for mcp_server core parsing and configuration logic.

Verifies:
- parse_brick_list: comma parsing, whitespace stripping, empty-input handling
- get_config: defaults and environment overrides
"""

from __future__ import annotations

import hypothesis.strategies as st
import pytest
from hypothesis import given, settings

from factory.mcp_server.core import get_config, parse_brick_list

_brick_name = st.text(
    min_size=1, max_size=20,
    alphabet=st.characters(whitelist_categories=("L", "N", "Pc")),
)
_brick_list = st.lists(_brick_name, min_size=0, max_size=15)
_SETTINGS = settings(max_examples=50)


# ── parse_brick_list ────────────────────────────────────────────────

@given(st.text(alphabet=" \t\n\r", max_size=20))
@_SETTINGS
def test_parse_empty_or_whitespace_returns_empty(ws):
    assert parse_brick_list(ws) == set()


@given(_brick_name)
@_SETTINGS
def test_parse_single_name(name):
    assert parse_brick_list(name) == {name}


@given(_brick_list)
@_SETTINGS
def test_parse_comma_separated_is_order_independent(names):
    raw = ", ".join(names)
    result = parse_brick_list(raw)
    assert result == {n.strip() for n in names if n.strip()}


@given(_brick_list)
@_SETTINGS
def test_parse_strips_whitespace(names):
    raw = " , ".join(f"  {n}  " for n in names)
    result = parse_brick_list(raw)
    assert "" not in result
    for n in names:
        if n.strip():
            assert n.strip() in result


@given(_brick_list)
@_SETTINGS
def test_parse_no_empty_strings_in_result(names):
    raw = ",".join(names)
    assert "" not in parse_brick_list(raw)


# ── get_config ──────────────────────────────────────────────────────

def test_get_config_defaults(monkeypatch):
    monkeypatch.delenv("MCP_SERVER_NAME", raising=False)
    monkeypatch.delenv("MCP_INCLUDE_BRICKS", raising=False)
    monkeypatch.delenv("MCP_EXCLUDE_BRICKS", raising=False)
    monkeypatch.delenv("MCP_DISCOVERY_MODE", raising=False)
    cfg = get_config()
    assert cfg["server_name"] == "factory-app"
    assert cfg["include_bricks"] == ""
    assert cfg["exclude_bricks"] == ""
    assert cfg["discovery_mode"] == "progressive"


def test_get_config_reads_env(monkeypatch):
    monkeypatch.setenv("MCP_SERVER_NAME", "my-srv")
    monkeypatch.setenv("MCP_INCLUDE_BRICKS", "a,b")
    cfg = get_config()
    assert cfg["server_name"] == "my-srv"
    assert cfg["include_bricks"] == "a,b"


def test_get_config_rejects_invalid_discovery_mode(monkeypatch):
    monkeypatch.setenv("MCP_DISCOVERY_MODE", "legacy")
    with pytest.raises(ValueError, match="progressive.*flat"):
        get_config()
