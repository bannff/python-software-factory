"""Crypto, isolation, and contract checks for owner-named secrets."""
from __future__ import annotations

import sqlite3

import pytest
from factory.mcp_utils.interface import TestKeyProvider

from factory.storage.runtime.adapters.owner_secrets_sqlite import SQLiteOwnerSecretStore
from factory.storage.runtime.ports.owner_secrets import (
    OwnerSecretError, OwnerSecretIdentity,
)


def ident(tenant: str = "tenant", principal: str = "owner") -> OwnerSecretIdentity:
    return OwnerSecretIdentity(tenant_id=tenant, principal_id=principal)


def test_identity_rejects_blank_or_missing_fields() -> None:
    with pytest.raises(OwnerSecretError):
        OwnerSecretIdentity(tenant_id="", principal_id="owner")
    with pytest.raises(OwnerSecretError):
        OwnerSecretIdentity(tenant_id="tenant", principal_id="   ")


def test_set_list_delete_round_trip(tmp_path) -> None:
    store = SQLiteOwnerSecretStore(str(tmp_path / "secrets.db"), TestKeyProvider())
    store.set_secret(ident(), "MY_API_KEY", "sk-abc123")
    assert store.list_names(ident()) == ["MY_API_KEY"]
    assert store.delete_secret(ident(), "MY_API_KEY") is True
    assert store.list_names(ident()) == []


def test_delete_missing_name_returns_false_not_error(tmp_path) -> None:
    store = SQLiteOwnerSecretStore(str(tmp_path / "secrets.db"), TestKeyProvider())
    assert store.delete_secret(ident(), "NEVER_SET") is False


def test_set_is_last_write_wins_overwrite_in_place(tmp_path) -> None:
    store = SQLiteOwnerSecretStore(str(tmp_path / "secrets.db"), TestKeyProvider())
    store.set_secret(ident(), "TOKEN", "first-value")
    store.set_secret(ident(), "TOKEN", "second-value")
    assert store.list_names(ident()) == ["TOKEN"]  # still one row, not two


def test_names_are_scoped_per_tenant_and_principal(tmp_path) -> None:
    store = SQLiteOwnerSecretStore(str(tmp_path / "secrets.db"), TestKeyProvider())
    store.set_secret(ident(principal="alice"), "SHARED_NAME", "alice-value")
    store.set_secret(ident(principal="bob"), "SHARED_NAME", "bob-value")
    assert store.list_names(ident(principal="alice")) == ["SHARED_NAME"]
    assert store.list_names(ident(principal="bob")) == ["SHARED_NAME"]
    # Deleting alice's does not touch bob's identically-named secret.
    assert store.delete_secret(ident(principal="alice"), "SHARED_NAME") is True
    assert store.list_names(ident(principal="bob")) == ["SHARED_NAME"]


def test_no_read_or_reveal_method_exists() -> None:
    """The port and adapter must never expose plaintext back out."""
    for forbidden in ("get_secret", "read_secret", "get", "read"):
        assert not hasattr(SQLiteOwnerSecretStore, forbidden)


def test_at_rest_ciphertext_never_contains_plaintext_value(tmp_path) -> None:
    path = tmp_path / "secrets.db"
    store = SQLiteOwnerSecretStore(str(path), TestKeyProvider())
    canary = "super-secret-plaintext-canary-value"
    store.set_secret(ident(), "CANARY_NAME", canary)
    with sqlite3.connect(path) as conn:
        rows = conn.execute("SELECT envelope, name FROM owner_secrets").fetchall()
    serialized = "".join(row[0] for row in rows)
    assert canary not in serialized
    # The name itself IS stored in plaintext in its own column (needed for
    # list_names), but never inside the encrypted envelope's ciphertext blob.
    assert rows[0][1] == "CANARY_NAME"


def test_value_size_over_limit_is_rejected_by_pydantic() -> None:
    from factory.storage.mcp.contracts.owner_secrets import OwnerSecretSetInput
    with pytest.raises(Exception):
        OwnerSecretSetInput.model_validate({"name": "X", "value": "a" * 65537})


def test_name_pattern_rejects_path_traversal_and_control_chars() -> None:
    from factory.storage.mcp.contracts.owner_secrets import OwnerSecretSetInput
    for bad_name in ("../etc/passwd", "name with space", "name\nwith\nnewline", ""):
        with pytest.raises(Exception):
            OwnerSecretSetInput.model_validate({"name": bad_name, "value": "v"})


def test_valid_name_charset_is_accepted() -> None:
    from factory.storage.mcp.contracts.owner_secrets import OwnerSecretSetInput
    parsed = OwnerSecretSetInput.model_validate({"name": "MY_API-KEY.v2", "value": "v"})
    assert parsed.name == "MY_API-KEY.v2"


def test_aad_binding_rejects_transplant_across_tenant_and_name() -> None:
    """Direct codec-level proof the AAD binding is load-bearing, not decorative.

    Sealing under (tenantA, nameX) must fail to open under a different tenant
    OR a different name — the exact ciphertext-transplant attack AAD binding
    exists to rule out (Gate A.5 nit: this property was previously proven
    only indirectly via SQL-layer isolation, never at the codec itself).
    """
    from factory.mcp_utils.interface import TestKeyProvider
    from factory.storage.runtime.adapters.aead_envelope import AeadEnvelopeCodec

    codec = AeadEnvelopeCodec(TestKeyProvider())

    def aad(tenant: str, principal: str, name: str, key_id: str) -> bytes:
        from factory.mcp_utils.interface import protected_canonical_json
        return protected_canonical_json({
            "v": "owner-secret-1", "tenant_id": tenant,
            "principal_id": principal, "name": name, "key_id": key_id,
        })

    sealed = codec.seal(lambda key_id: aad("tenantA", "owner", "nameX", key_id), {"value": "v"})

    # Same tenant+principal, different name: must fail.
    with pytest.raises(Exception):
        codec.open(lambda key_id: aad("tenantA", "owner", "nameY", key_id), sealed)
    # Different tenant, same name: must fail.
    with pytest.raises(Exception):
        codec.open(lambda key_id: aad("tenantB", "owner", "nameX", key_id), sealed)
    # Exact original AAD: must succeed and round-trip the plaintext.
    assert codec.open(lambda key_id: aad("tenantA", "owner", "nameX", key_id), sealed) == {"value": "v"}
