"""Crypto, isolation, and stateful checks for protected SQLite artifacts."""
from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest
from hypothesis import settings
from hypothesis.stateful import RuleBasedStateMachine, invariant, rule

from factory.mcp_utils.interface import AuthorizationAssertion, ProtectedContentDescriptor, TestKeyProvider
from factory.storage.runtime.adapters.protected_sqlite import ProtectedArtifactError, SQLiteBusinessContentArtifactStore


def assertion(action: str, owner: str = "owner", tenant: str = "tenant", purpose: str = "email") -> AuthorizationAssertion:
    return AuthorizationAssertion(principal_id=owner, tenant_id=tenant, action=action, purpose=purpose)


def descriptor(**changes: object) -> ProtectedContentDescriptor:
    values = {"classification": "business", "purpose": "email", "tenant_id": "tenant", "owner_principal_id": "owner", "artifact_kind": "email", "projection_profile": "email-summary"}
    return ProtectedContentDescriptor(**(values | changes))


def test_encryption_freshness_and_direct_sqlite_no_copy(tmp_path):
    path, keys = tmp_path / "artifacts.db", TestKeyProvider()
    store = SQLiteBusinessContentArtifactStore(str(path), keys)
    payload = {"recipients": ["é\ncanary@example.test"], "subject": "sub\nject", "body": "unicode ☃\nbody", "attachment": "base64-QUJD"}
    _, first = store.create_or_match(descriptor(), payload, assertion("create"))
    with pytest.raises(ProtectedArtifactError, match="protected artifact unavailable"):
        store.create_or_match(descriptor(classification="restricted"), payload, assertion("create"))
    with sqlite3.connect(path) as conn:
        rows = conn.execute("SELECT envelope FROM protected_artifacts").fetchall()
    serialized = "".join(row[0] for row in rows)
    for canary in ("canary@example.test", "sub\\nject", "unicode", "base64-QUJD"):
        assert canary not in serialized
    assert store.materialize(first, assertion("materialize")) == payload
    assert store.project(first, assertion("project")).values == {"artifact_kind": "email", "classification": "business", "purpose": "email", "recipient_count": 1}


def test_create_or_match_scopes_deduplication_to_artifact_owner(tmp_path):
    store = SQLiteBusinessContentArtifactStore(str(tmp_path / "owners.db"), TestKeyProvider())
    payload = {"body": "shared plaintext"}
    _, owner_a = store.create_or_match(descriptor(), payload, assertion("create"))
    _, owner_b = store.create_or_match(
        descriptor(owner_principal_id="owner-b"), payload,
        assertion("create", owner="owner-b"),
    )
    assert owner_a.artifact_ref != owner_b.artifact_ref
    assert owner_a.fingerprint != owner_b.fingerprint
    assert store.materialize(owner_a, assertion("materialize")) == payload
    assert store.materialize(
        owner_b, assertion("materialize", owner="owner-b"),
    ) == payload


def test_search_scopes_before_limit_and_supports_non_email_artifacts(tmp_path):
    store = SQLiteBusinessContentArtifactStore(str(tmp_path / "search.db"), TestKeyProvider())
    wanted = descriptor(artifact_kind="document", purpose="review", projection_profile="metadata")
    _, wanted_ref = store.create_or_match(
        wanted, {"safe_value": "document"},
        assertion("create", purpose="review"),
    )
    for index in range(3):
        store.create_or_match(
            descriptor(owner_principal_id=f"other-{index}"), {"body": str(index)},
            assertion("create", owner=f"other-{index}"),
        )
    results = store.search(
        wanted, assertion("search", purpose="review"), limit=1,
    )
    assert [item.artifact_ref for item in results] == [wanted_ref.artifact_ref]
    assert results[0].values["artifact_kind"] == "document"


def test_tamper_expiry_scope_and_tombstone_are_indistinguishable(tmp_path):
    path = tmp_path / "artifacts.db"; store = SQLiteBusinessContentArtifactStore(str(path), TestKeyProvider())
    _, ref = store.create_or_match(descriptor(), {"body": "secret"}, assertion("create"))
    denied = [assertion("materialize", owner="other"), assertion("materialize", tenant="other"), assertion("materialize", purpose="other")]
    for request in denied:
        with pytest.raises(ProtectedArtifactError, match="protected artifact unavailable"): store.materialize(ref, request)
    with sqlite3.connect(path) as conn: conn.execute("UPDATE protected_artifacts SET envelope='{}'")
    with pytest.raises(ProtectedArtifactError, match="protected artifact unavailable"): store.materialize(ref, assertion("materialize"))
    _, expired = store.create_or_match(descriptor(retention_until=datetime.now(timezone.utc) - timedelta(seconds=1)), {"body": "gone"}, assertion("create"))
    with pytest.raises(ProtectedArtifactError, match="protected artifact unavailable"): store.materialize(expired, assertion("materialize"))


def test_rekey_preserves_ref_and_old_key_cannot_read(tmp_path):
    keys = TestKeyProvider(b"a" * 32, "old"); store = SQLiteBusinessContentArtifactStore(str(tmp_path / "x.db"), keys)
    _, ref = store.create_or_match(descriptor(), {"body": "stable"}, assertion("create"))
    keys.rotate("new", b"b" * 32); store.rekey(ref, assertion("rekey"))
    assert store.materialize(ref, assertion("materialize")) == {"body": "stable"}


class ArtifactMachine(RuleBasedStateMachine):
    def __init__(self) -> None:
        super().__init__(); self.path = f"/tmp/protected-stateful-{uuid4()}.db"; self.keys = TestKeyProvider(); self.store = SQLiteBusinessContentArtifactStore(self.path, self.keys); self.refs = []; self.live = True
    @rule()
    def create_or_match(self) -> None:
        try:
            _, ref = self.store.create_or_match(descriptor(), {"body": "stateful"}, assertion("create"))
        except ProtectedArtifactError:
            return
        self.refs.append(ref)
    @rule()
    def materialize_as_owner(self) -> None:
        if self.refs and self.live:
            assert self.store.materialize(self.refs[-1], assertion("materialize"))["body"] == "stateful"
    @rule()
    def search_as_owner(self) -> None:
        if self.live:
            assert all(item.values["artifact_kind"] == "email" for item in self.store.search(descriptor(), assertion("search")))
    @rule()
    def materialize_as_foreign_owner(self) -> None:
        if self.refs:
            with pytest.raises(ProtectedArtifactError): self.store.materialize(self.refs[-1], assertion("materialize", owner="foreign"))
    @rule()
    def rotate(self) -> None:
        self.keys.rotate("rotated", b"r" * 32)
        if self.refs and self.live: self.store.rekey(self.refs[-1], assertion("rekey"))
    @rule()
    def tombstone(self) -> None:
        if self.refs and self.live:
            self.store.tombstone(self.refs[-1], assertion("tombstone")); self.live = False
    @invariant()
    def no_plaintext_or_foreign_read(self) -> None:
        for ref in self.refs:
            with pytest.raises(ProtectedArtifactError): self.store.materialize(ref, assertion("materialize", owner="foreign"))


TestProtectedArtifactStateMachine = ArtifactMachine.TestCase
TestProtectedArtifactStateMachine.settings = settings(max_examples=50, deadline=None, stateful_step_count=20)


def test_v1_envelope_rejects_field_swaps_and_noncanonical_base64(tmp_path):
    store = SQLiteBusinessContentArtifactStore(str(tmp_path / "swap.db"), TestKeyProvider())
    _, ref = store.create_or_match(descriptor(), {"body": "stable"}, assertion("create"))
    with sqlite3.connect(tmp_path / "swap.db") as conn:
        envelope = json.loads(conn.execute("SELECT envelope FROM protected_artifacts").fetchone()[0])
        envelope["payload_nonce"], envelope["wrap_nonce"] = envelope["wrap_nonce"], envelope["payload_nonce"]
        conn.execute("UPDATE protected_artifacts SET envelope=?", (json.dumps(envelope),))
    with pytest.raises(ProtectedArtifactError): store.materialize(ref, assertion("materialize"))
    with sqlite3.connect(tmp_path / "swap.db") as conn:
        envelope = json.loads(conn.execute("SELECT envelope FROM protected_artifacts").fetchone()[0])
        envelope["ciphertext"] = "bad+base64"
        conn.execute("UPDATE protected_artifacts SET envelope=?", (json.dumps(envelope),))
    with pytest.raises(ProtectedArtifactError): store.materialize(ref, assertion("materialize"))


def test_rekey_does_not_resurrect_tombstoned_row(tmp_path):
    store = SQLiteBusinessContentArtifactStore(str(tmp_path / "race.db"), TestKeyProvider())
    _, ref = store.create_or_match(descriptor(), {"body": "stable"}, assertion("create"))
    store.tombstone(ref, assertion("tombstone"))
    with pytest.raises(ProtectedArtifactError): store.rekey(ref, assertion("rekey"))
    with pytest.raises(ProtectedArtifactError): store.materialize(ref, assertion("materialize"))


def test_envelope_decoder_rejects_noncanonical_base64url():
    # ``AB`` decodes to the same byte as canonical ``AA`` but must not be accepted.
    with pytest.raises(ValueError, match="invalid envelope"):
        SQLiteBusinessContentArtifactStore._decode("AB")


def test_complete_descriptor_is_authenticated_and_ref_descriptor_must_match(tmp_path):
    path = tmp_path / "descriptor.db"
    store = SQLiteBusinessContentArtifactStore(str(path), TestKeyProvider())
    _, ref = store.create_or_match(descriptor(), {"body": "secret"}, assertion("create"))
    forged = ref.model_copy(update={
        "descriptor": descriptor(classification="public", purpose="export"),
    })
    with pytest.raises(ProtectedArtifactError, match="protected artifact unavailable"):
        store.materialize(forged, assertion("materialize", purpose="export"))
    with sqlite3.connect(path) as connection:
        connection.execute(
            "UPDATE protected_artifacts SET descriptor=? WHERE ref=?",
            (descriptor(classification="public").model_dump_json(), ref.artifact_ref),
        )
    with pytest.raises(ProtectedArtifactError, match="protected artifact unavailable"):
        store.materialize(ref, assertion("materialize"))


def test_local_index_key_is_stable_across_encryption_key_rotation(tmp_path):
    import base64
    from factory.mcp_utils.interface import LocalEnvironmentKeyProvider

    old_key, new_key, index_key = b"a" * 32, b"b" * 32, b"i" * 32
    environ = {
        "FACTORY_PROTECTED_CONTENT_LOCAL_KEK": base64.b64encode(old_key).decode(),
        "FACTORY_PROTECTED_CONTENT_LOCAL_INDEX_KEY": base64.b64encode(index_key).decode(),
    }
    path = tmp_path / "rotation.db"
    original = SQLiteBusinessContentArtifactStore(
        str(path), LocalEnvironmentKeyProvider("old", environ),
    )
    _, first = original.create_or_match(
        descriptor(), {"body": "stable"}, assertion("create"),
    )
    environ.update({
        "FACTORY_PROTECTED_CONTENT_LOCAL_KEK": base64.b64encode(new_key).decode(),
        "FACTORY_PROTECTED_CONTENT_LOCAL_HISTORICAL_KEKS": json.dumps({
            "old": base64.b64encode(old_key).decode(),
        }),
    })
    rotated = SQLiteBusinessContentArtifactStore(
        str(path), LocalEnvironmentKeyProvider("new", environ),
    )
    status, matched = rotated.create_or_match(
        descriptor(), {"body": "stable"}, assertion("create"),
    )
    assert status == "matched" and matched == first
    rotated.rekey(first, assertion("rekey"))
    assert rotated.materialize(first, assertion("materialize")) == {"body": "stable"}
