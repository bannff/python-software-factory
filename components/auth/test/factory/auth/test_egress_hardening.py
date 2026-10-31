"""tntt0: route value-schema, secret redaction, SSRF-pinned HTTP egress."""
from __future__ import annotations

import httpx

from factory.auth.runtime.egress_models import (
    ProviderRoute, redact_secrets, request_digest,
)
from factory.auth.runtime.egress_registry import resolve_route
from factory.auth.runtime.adapters.http_egress import HttpProviderEgress


# ---- value-schema --------------------------------------------------------

def test_route_rejects_unknown_field():
    route = resolve_route("microsoft", "send_mail")
    assert not route.validate_payload({"subject": "s", "cc": "evil@x.z"})


def test_route_rejects_wrong_value_type():
    route = resolve_route("microsoft", "list_messages")  # top:int
    assert route.validate_payload({"top": 5})
    assert not route.validate_payload({"top": "5"})   # str where int required
    assert not route.validate_payload({"top": True})  # bool is not an int here


def test_route_rejects_oversized_string():
    route = resolve_route("microsoft", "send_mail")
    assert not route.validate_payload({"subject": "x" * 9000})


def test_schema_field_must_be_in_allowed_fields():
    import pytest
    with pytest.raises(ValueError):
        ProviderRoute(
            provider_id="p", route_id="r", origin="https://x.test", method="POST",
            path_template="/", required_scopes=(), allowed_fields=frozenset({"a"}),
            request_schema=(("b", "str"),), secret_slot_kind="client_secret")


# ---- secret redaction ----------------------------------------------------

def test_redact_secrets_drops_token_named_fields_recursively():
    dirty = {"ok": True, "access_token": "fat_x", "nested": {
        "refresh_token": "r", "keep": 1}, "list": [{"secret": "s", "v": 2}]}
    clean = redact_secrets(dirty)
    assert clean == {"ok": True, "nested": {"keep": 1}, "list": [{"v": 2}]}


# ---- SSRF-pinned HTTP egress transport -----------------------------------

def _route():
    return resolve_route("microsoft", "send_mail")


def _client(handler):
    return httpx.Client(transport=httpx.MockTransport(handler))


def test_http_egress_ok_injects_bearer_and_redacts():
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["auth"] = request.headers.get("authorization")
        seen["url"] = str(request.url)
        return httpx.Response(200, json={"id": "msg-1", "access_token": "leak"})

    status, data = HttpProviderEgress(_client(handler)).call(
        _route(), "tok-123", {"subject": "s", "body": "b", "to": "x@y.z"})
    assert status == "ok" and data == {"id": "msg-1"}  # token field redacted
    assert seen["auth"] == "Bearer tok-123"
    assert seen["url"] == "https://graph.microsoft.com/v1.0/me/sendMail"


def test_http_egress_refuses_redirect():
    def handler(request):
        return httpx.Response(302, headers={"location": "https://evil.test/steal"})
    status, data = HttpProviderEgress(_client(handler)).call(_route(), "t", {})
    assert status == "denied" and data == {}


def test_http_egress_caps_response_bytes():
    def handler(request):
        return httpx.Response(200, json={"blob": "y" * 100_000})
    status, _ = HttpProviderEgress(_client(handler)).call(_route(), "t", {})
    assert status == "denied"


def test_http_egress_maps_401_to_unauthorized():
    def handler(request):
        return httpx.Response(401, json={"error": "invalid_token"})
    status, _ = HttpProviderEgress(_client(handler)).call(_route(), "t", {})
    assert status == "unauthorized"


def test_http_egress_get_uses_query_params():
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        return httpx.Response(200, json={"value": []})

    status, _ = HttpProviderEgress(_client(handler)).call(
        resolve_route("microsoft", "list_messages"), "t", {"top": 5})
    assert status == "ok" and "top=5" in seen["url"]
