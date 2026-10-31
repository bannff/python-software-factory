"""Public owner-secret MCP boundary tests: identity, isolation, fail-closed."""
from __future__ import annotations

import asyncio

from factory.mcp_utils.interface import TestKeyProvider, reset_envelope, set_envelope
from factory.storage.runtime.runtime import StorageRuntime
from factory.storage.server import create_tool_catalog


def _fixture(tmp_path):
    runtime = StorageRuntime({"owner_secret_db_path": str(tmp_path / "owner-secrets.db")})
    runtime.get_owner_secret_store(keys=TestKeyProvider())
    return create_tool_catalog(runtime)


def _call(catalog, name: str, arguments: dict, *, envelope: dict | None):
    tool = asyncio.run(catalog.get_tool(name))
    token = set_envelope(envelope) if envelope is not None else None
    try:
        return tool.fn(**arguments)
    finally:
        reset_envelope(token)


_OWNER_A = {"principal_id": "owner-a", "tenant_id": "tenant"}
_OWNER_B = {"principal_id": "owner-b", "tenant_id": "tenant"}


def test_owner_secret_tools_are_registered_publicly(tmp_path) -> None:
    catalog = _fixture(tmp_path)
    for name in ("storage.owner_secret_list", "storage.owner_secret_set",
                 "storage.owner_secret_delete"):
        assert asyncio.run(catalog.get_tool(name)) is not None


def test_set_list_delete_round_trip_through_mcp(tmp_path) -> None:
    catalog = _fixture(tmp_path)
    set_result = _call(catalog, "storage.owner_secret_set",
                        {"name": "API_KEY", "value": "sk-123"}, envelope=_OWNER_A)
    assert set_result.ok and set_result.data.ok is True and set_result.data.name == "API_KEY"

    listed = _call(catalog, "storage.owner_secret_list", {}, envelope=_OWNER_A)
    assert listed.ok and listed.data.names == ["API_KEY"]

    deleted = _call(catalog, "storage.owner_secret_delete", {"name": "API_KEY"}, envelope=_OWNER_A)
    assert deleted.ok and deleted.data.ok is True

    listed_after = _call(catalog, "storage.owner_secret_list", {}, envelope=_OWNER_A)
    assert listed_after.ok and listed_after.data.names == []


def test_list_never_returns_values_only_names(tmp_path) -> None:
    catalog = _fixture(tmp_path)
    _call(catalog, "storage.owner_secret_set",
          {"name": "TOKEN", "value": "plaintext-value-canary"}, envelope=_OWNER_A)
    listed = _call(catalog, "storage.owner_secret_list", {}, envelope=_OWNER_A)
    dumped = listed.data.model_dump()
    assert "plaintext-value-canary" not in str(dumped)
    assert dumped == {"names": ["TOKEN"]}


def test_owners_are_isolated_from_each_others_secrets(tmp_path) -> None:
    catalog = _fixture(tmp_path)
    _call(catalog, "storage.owner_secret_set",
          {"name": "SHARED_NAME", "value": "a-value"}, envelope=_OWNER_A)
    _call(catalog, "storage.owner_secret_set",
          {"name": "SHARED_NAME", "value": "b-value"}, envelope=_OWNER_B)

    a_list = _call(catalog, "storage.owner_secret_list", {}, envelope=_OWNER_A)
    b_list = _call(catalog, "storage.owner_secret_list", {}, envelope=_OWNER_B)
    assert a_list.data.names == ["SHARED_NAME"]
    assert b_list.data.names == ["SHARED_NAME"]

    # B deleting does not remove A's identically-named secret.
    _call(catalog, "storage.owner_secret_delete", {"name": "SHARED_NAME"}, envelope=_OWNER_B)
    a_list_after = _call(catalog, "storage.owner_secret_list", {}, envelope=_OWNER_A)
    assert a_list_after.data.names == ["SHARED_NAME"]


def test_missing_envelope_fails_closed_not_shared_namespace(tmp_path) -> None:
    catalog = _fixture(tmp_path)
    result = _call(catalog, "storage.owner_secret_list", {}, envelope=None)
    assert result.ok is False and result.error == "owner_secret_unavailable"

    set_result = _call(catalog, "storage.owner_secret_set", {"name": "X", "value": "v"}, envelope=None)
    assert set_result.ok is False and set_result.error == "owner_secret_unavailable"


def test_blank_principal_id_in_envelope_fails_closed(tmp_path) -> None:
    catalog = _fixture(tmp_path)
    result = _call(catalog, "storage.owner_secret_list", {},
                    envelope={"principal_id": "", "tenant_id": "tenant"})
    assert result.ok is False and result.error == "owner_secret_unavailable"


def test_delete_missing_name_reports_ok_false_not_an_error(tmp_path) -> None:
    catalog = _fixture(tmp_path)
    result = _call(catalog, "storage.owner_secret_delete", {"name": "NEVER_SET"}, envelope=_OWNER_A)
    assert result.ok is True and result.data.ok is False


def test_no_read_or_reveal_tool_exists(tmp_path) -> None:
    catalog = _fixture(tmp_path)
    for forbidden in ("storage.owner_secret_get", "storage.owner_secret_read",
                      "storage.owner_secret_reveal"):
        assert asyncio.run(catalog.get_tool(forbidden)) is None
