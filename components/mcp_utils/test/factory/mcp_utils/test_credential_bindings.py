"""Unit tests for the credential_slot / credential_egress service bindings."""
from __future__ import annotations

import pytest

from factory.mcp_utils.interface import (
    CredentialEgressBinding, CredentialSlotBinding, service_only,
)
from factory.mcp_utils.service_bindings import binding_kind, binding_matches

_DIGEST = "a" * 64


def _slot(**over):
    base = dict(tenant_id="t", owner_id="o", provider_id="microsoft",
                connection_ref="c", slot_kind="refresh_token", generation=1)
    base.update(over)
    return CredentialSlotBinding(**base)


def test_slot_binding_kind_and_validation():
    assert binding_kind(_slot()) == "credential_slot"
    with pytest.raises(ValueError):
        _slot(slot_kind="bogus")
    with pytest.raises(ValueError):
        _slot(generation=0)
    with pytest.raises(ValueError):
        _slot(tenant_id="")


def test_egress_binding_kind_and_validation():
    b = CredentialEgressBinding(provider_id="adobe", route_id="r", connection_ref="c",
                                request_digest=_DIGEST)
    assert binding_kind(b) == "credential_egress"
    with pytest.raises(ValueError):
        CredentialEgressBinding(provider_id="a", route_id="r", connection_ref="c",
                                request_digest="short")


def test_slot_binding_matches_nested_slot_arguments():
    b = _slot()
    good = {"slot": {"tenant_id": "t", "owner_id": "o", "provider_id": "microsoft",
                     "connection_ref": "c", "slot_kind": "refresh_token", "generation": 1},
            "secret": {"refresh_token": "x"}}
    assert binding_matches(b, good)
    bad = {"slot": {**good["slot"], "generation": 2}}
    assert not binding_matches(b, bad)
    assert not binding_matches(b, {"secret": {}})  # no slot object


def test_egress_binding_matches_nested_request_arguments():
    b = CredentialEgressBinding(provider_id="microsoft", route_id="send_mail",
                                connection_ref="c1", request_digest=_DIGEST)
    good = {"request": {"provider_id": "microsoft", "route_id": "send_mail",
                        "connection_ref": "c1", "request_digest": _DIGEST,
                        "payload": {"subject": "s"}}}
    assert binding_matches(b, good)
    bad = {"request": {**good["request"], "connection_ref": "other"}}
    assert not binding_matches(b, bad)


def test_service_only_accepts_new_binding_kinds():
    for kind in ("credential_slot", "credential_egress"):
        @service_only(callers={"auth"}, binding=kind)
        def _tool():  # pragma: no cover - decoration only
            return None
    with pytest.raises(ValueError):
        service_only(callers={"auth"}, binding="bogus")(lambda: None)
