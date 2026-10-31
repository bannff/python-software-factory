"""Connections models and owner-scoped CAS store."""
from __future__ import annotations

import json

import pytest
from hypothesis import given, strategies as st
from pydantic import ValidationError

from factory.connections.runtime.adapters.server_store_sqlite import SqliteServerStore
from factory.connections.runtime.models import ServerSpec, ServersDocument, StaleServer

STDIO = {"command": "uvx", "args": ["some-server"], "env": {"API_TOKEN": "MY_TOKEN_ENV"}}
HTTP = {"transport": "streamable_http", "url": "https://example.test/mcp",
        "headers": {"Authorization": "EXAMPLE_BEARER_ENV"}}


def test_document_parses_standard_mcp_servers_shape() -> None:
    doc = ServersDocument.model_validate(json.loads(json.dumps({"mcpServers": {"a": STDIO, "b": HTTP}})))
    assert doc.mcpServers["a"].transport == "stdio"
    assert doc.mcpServers["b"].transport == "streamable_http"


@pytest.mark.parametrize("bad", [
    {"command": "x", "url": "https://e/mcp"},                      # mixed transports
    {"transport": "streamable_http", "url": "ftp://e/mcp"},        # scheme
    {"command": "x", "env": {"API_TOKEN": "sk-live-abc123"}},      # value, not env name
    {"transport": "streamable_http", "url": "https://e", "headers": {"Authorization": "Bearer x"}},
    {"command": "x", "unknown": 1},                                # extra forbidden
])
def test_secret_values_and_malformed_specs_are_rejected(bad: dict) -> None:
    with pytest.raises((ValidationError, ValueError)):
        ServerSpec.model_validate(bad)


@given(st.text(min_size=1, max_size=70))
def test_names_are_bounded_identifiers(name: str) -> None:
    import re
    ok = bool(re.fullmatch(r"^[a-z0-9][a-z0-9_-]{0,63}$", name))
    try:
        ServersDocument.model_validate({"mcpServers": {name: STDIO}})
    except (ValidationError, ValueError):
        assert not ok
    else:
        assert ok


def test_store_is_owner_scoped_with_revision_cas(tmp_path) -> None:
    store = SqliteServerStore(tmp_path / "c.db")
    spec = ServerSpec.model_validate(STDIO)
    created = store.upsert("t", "owner-a", "a", spec, None)
    assert created.revision == 1
    assert store.list("t", "owner-b") == ()
    assert store.get("t", "owner-a", "a") == created
    with pytest.raises(StaleServer):
        store.upsert("t", "owner-a", "a", spec, None)          # already exists
    with pytest.raises(StaleServer):
        store.upsert("t", "owner-a", "a", spec, 7)             # wrong revision
    updated = store.upsert("t", "owner-a", "a", ServerSpec.model_validate(HTTP), 1)
    assert updated.revision == 2 and updated.spec.transport == "streamable_http"
    with pytest.raises(StaleServer):
        store.remove("t", "owner-a", "a", 1)
    assert store.remove("t", "owner-a", "a", 2) is True
    assert store.list("t", "owner-a") == ()
