"""Frozen dcal/v1 canonical JSON, timestamp, digest, and signature payload behavior."""
from __future__ import annotations

import pytest

from factory.blockchain.runtime.dcal.canonical import (
    MAX_BYTES, MAX_COLLECTION, MAX_DEPTH, MAX_STRING_BYTES, build_signable_message,
    canonical_digest, canonical_json_bytes, canonical_json_text, parse_canonical_json,
    parse_rfc3339_utc_microseconds, sha256_domain,
)


@pytest.mark.parametrize("text", ('{"a":1,"a":2}', '{"a":{"x":1,"x":2}}'))
def test_duplicate_root_and_nested_keys_are_rejected_before_dto_work(text: str) -> None:
    with pytest.raises(ValueError): parse_canonical_json(text)


@pytest.mark.parametrize("value", ('{"a":1.0}', '{"a":NaN}', '{"a":Infinity}', b'\xff', {"a": b"x"}))
def test_float_nonfinite_and_binary_values_are_rejected(value: object) -> None:
    with pytest.raises((TypeError, ValueError)):
        parse_canonical_json(value) if isinstance(value, (str, bytes)) else canonical_json_bytes(value)


def test_raw_text_and_bytes_limits_apply_before_json_parsing() -> None:
    with pytest.raises(ValueError, match="raw JSON"):
        parse_canonical_json("{" + "x" * MAX_BYTES)
    with pytest.raises(ValueError, match="raw JSON"):
        parse_canonical_json(b"{" + b"x" * MAX_BYTES)


def test_nfc_key_order_null_and_omission_are_frozen() -> None:
    assert canonical_json_bytes({"value": "café"}) == canonical_json_bytes({"value": "cafe\u0301"})
    with pytest.raises(ValueError, match="NFC"): canonical_json_bytes({"café": 1, "cafe\u0301": 2})
    assert canonical_json_text({"z": 1, "a": 2}) == canonical_json_text({"a": 2, "z": 1})
    assert canonical_json_bytes({"present": None}) != canonical_json_bytes({})


def test_one_over_structural_limits_are_rejected() -> None:
    with pytest.raises(ValueError): canonical_json_bytes({"x": "x" * (MAX_STRING_BYTES + 1)})
    with pytest.raises(ValueError): canonical_json_bytes(list(range(MAX_COLLECTION + 1)))
    nested: object = 0
    for _ in range(MAX_DEPTH): nested = [nested]
    with pytest.raises(ValueError): canonical_json_bytes(nested)
    with pytest.raises(ValueError): canonical_json_bytes({"x": "x" * MAX_BYTES})


@pytest.mark.parametrize("value", ("2026-08-21T12:34:56.123456Z",))
def test_rfc3339_utc_microseconds_accepts_only_the_explicit_typed_format(value: str) -> None:
    assert parse_rfc3339_utc_microseconds(value).microsecond == 123456


@pytest.mark.parametrize("value", ("2026-08-21T12:34:56Z", "2026-08-21T12:34:56.12345Z", "2026-08-21T12:34:56.123456+00:00", "timestamp"))
def test_rfc3339_utc_microseconds_rejects_near_misses(value: str) -> None:
    with pytest.raises(ValueError): parse_rfc3339_utc_microseconds(value)


def test_domain_tags_are_allowlisted_and_signable_bindings_are_complete() -> None:
    payload = canonical_json_bytes({"operation": "recorded"})
    assert sha256_domain("record", payload) != sha256_domain("idempotency", payload)
    with pytest.raises(ValueError): sha256_domain("arbitrary", payload)
    base = dict(purpose="signature", tenant_id="tenant-1", ledger_id="ledger-1", policy_digest="a" * 64,
                canonical_digest=canonical_digest({"operation": "recorded"}, domain_tag="record"))
    message = build_signable_message(**base)
    for field in base:
        changed = {**base, field: "idempotency" if field == "purpose" else f"changed-{base[field]}"}
        assert build_signable_message(**changed) != message
    with pytest.raises(ValueError): build_signable_message(**{**base, "purpose": "arbitrary"})


def test_fixed_fixture_golden_vector_is_stable() -> None:
    value = {"tenant": "tenant-1", "operation": "recorded", "sequence": 7}
    canonical = canonical_json_bytes(value)
    digest = canonical_digest(value, domain_tag="record")
    message = build_signable_message(purpose="signature", tenant_id="tenant-1", ledger_id="ledger-1",
        policy_digest="a" * 64, canonical_digest=digest)
    assert canonical == b'{"operation":"recorded","sequence":7,"tenant":"tenant-1"}'
    assert digest == "1fcba528d15c1c2e73864ce28094c402816467f185491a9e5f00fa438f1def93"
    assert message == b'{"canonical_digest":"1fcba528d15c1c2e73864ce28094c402816467f185491a9e5f00fa438f1def93","ledger_id":"ledger-1","policy_digest":"aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa","profile":"dcal","protocol":"dcal","purpose":"signature","tenant_id":"tenant-1","version":"v1"}'
