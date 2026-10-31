"""eqrh4: OAuth authorization-code enrollment end-to-end, fully offline.

begin -> (simulated provider) -> complete exchanges code->refresh_token ->
broker.enroll writes it to the vault -> a subsequent egress send acquires an
access token from the (mock) token endpoint and calls the (mock) provider. No
real network, no app registration: a MockTransport serves the token + egress
endpoints, and a test OAuth provider carries a fake client_id.
"""
from __future__ import annotations

import asyncio
import urllib.parse

import httpx
import pytest

from factory.mcp_server.runtime.aggregator import MCPAggregator
from factory.mcp_server.runtime.native_invoker import NativeEnvelopeInvoker
from factory.mcp_utils import registry as service_registry
from factory.mcp_utils.interface import TestKeyProvider, reset_envelope, set_envelope
from factory.mcp_utils.runtime.tool_catalog import ToolCatalog
from factory.auth.server import create_tool_catalog as auth_catalog
from factory.auth.runtime.credential_broker import CredentialBroker
from factory.auth.runtime.adapters.http_token_acquirer import HttpProvider
from factory.auth.runtime.adapters.oauth_code_exchanger import OAuthCodeExchanger
from factory.auth.runtime.adapters.secret_store_service import ServiceSecretStore
from factory.auth.runtime.egress_models import ProviderRoute, SlotCoordinate
from factory.auth.runtime.egress_registry import register_route, resolve_route
from factory.auth.runtime.enrollment_state import InMemoryEnrollmentStateStore
from factory.auth.runtime.oauth_provider_registry import (
    OAuthProvider, register_oauth_provider,
)
from factory.storage.runtime.runtime import StorageRuntime
from factory.storage.server import create_tool_catalog as storage_catalog

REFRESH = "rt-REAL-CANARY-111"
ACCESS = "at-REAL-CANARY-222"
PROVIDER = "msft_test"


def _handler(request: httpx.Request) -> httpx.Response:
    url = str(request.url)
    if url == "https://login.test/token":
        form = urllib.parse.parse_qs(request.content.decode())
        grant = form.get("grant_type", [""])[0]
        if grant == "authorization_code":
            return httpx.Response(200, json={"refresh_token": REFRESH})
        if grant == "refresh_token":
            return httpx.Response(200, json={"access_token": ACCESS, "expires_in": 3600})
    if url == "https://graph.test/v1.0/me/sendMail":
        return httpx.Response(200, json={"id": "msg-1"})
    return httpx.Response(404, json={})


@pytest.fixture
def rig(tmp_path, monkeypatch):
    register_oauth_provider(OAuthProvider(
        provider_id=PROVIDER, authorize_url="https://login.test/authorize",
        token_url="https://login.test/token", scopes=("offline_access", "Mail.Send"),
        redirect_uris=frozenset({"http://localhost:8000/oauth/callback"}),
        client_id="test-client"))
    register_route(ProviderRoute(
        provider_id=PROVIDER, route_id="send_mail", origin="https://graph.test",
        method="POST", path_template="/v1.0/me/sendMail", required_scopes=("Mail.Send",),
        allowed_fields=frozenset({"subject", "body", "to"}),
        request_schema=(("subject", "str"), ("body", "str"), ("to", "str")),
        secret_slot_kind="refresh_token"))
    runtime = StorageRuntime({"credential_slot_db_path": str(tmp_path / "slots.db")})
    runtime.get_credential_slot_store(keys=TestKeyProvider())
    agg = MCPAggregator(ToolCatalog("root"))
    agg.set_available_bricks(["auth", "storage"])
    auth = auth_catalog()
    agg._lazy._cache["auth"] = auth
    agg._lazy._cache["storage"] = storage_catalog(runtime)
    native = NativeEnvelopeInvoker(agg)
    client = httpx.Client(transport=httpx.MockTransport(_handler))
    svc = service_registry._services
    monkeypatch.setitem(svc, "tool_invoker_for_caller", native.for_caller)
    monkeypatch.setitem(svc, "enrollment_state_store", InMemoryEnrollmentStateStore())
    monkeypatch.setitem(svc, "oauth_code_exchanger", OAuthCodeExchanger(client))
    broker = CredentialBroker(ServiceSecretStore(), {PROVIDER: HttpProvider(client)})
    monkeypatch.setitem(svc, "credential_broker", broker)
    return auth, broker


def _fn(catalog, name):
    return asyncio.run(catalog.get_tool(name)).fn


def _begin(auth, **kw):
    token = set_envelope({"principal_id": "o1", "tenant_id": "t1"})
    try:
        return _fn(auth, "auth.oauth_enroll_begin")(**kw)
    finally:
        reset_envelope(token)


def test_begin_returns_authorize_url_with_pkce_and_state(rig):
    auth, _ = rig
    res = _begin(auth, provider_id=PROVIDER, connection_ref="c1")
    assert res.ok
    url = res.data.authorize_url
    assert url.startswith("https://login.test/authorize?")
    assert "client_id=test-client" in url and "code_challenge_method=S256" in url
    assert f"state={res.data.state}" in url and REFRESH not in url


def test_full_enroll_then_send_works(rig):
    auth, broker = rig
    begin = _begin(auth, provider_id=PROVIDER, connection_ref="c1")
    done = _fn(auth, "auth.oauth_enroll_complete")(state=begin.data.state, code="auth-code")
    assert done.ok and done.data.status == "connected" and done.data.generation == 1
    assert REFRESH not in done.model_dump_json() and ACCESS not in done.model_dump_json()
    # the enrolled account can now actually send through the egress rail
    coord = SlotCoordinate("t1", "o1", PROVIDER, "c1", "refresh_token")
    result = broker.egress(coord, resolve_route(PROVIDER, "send_mail"),
                           {"subject": "s", "body": "b", "to": "x@y.z"})
    assert result.status == "ok"
    assert REFRESH not in result.model_dump_json() and ACCESS not in result.model_dump_json()


def test_state_is_single_use(rig):
    auth, _ = rig
    begin = _begin(auth, provider_id=PROVIDER, connection_ref="c1")
    first = _fn(auth, "auth.oauth_enroll_complete")(state=begin.data.state, code="c1")
    assert first.ok
    replay = _fn(auth, "auth.oauth_enroll_complete")(state=begin.data.state, code="c2")
    assert replay.ok is False and replay.error == "invalid_or_expired_state"


def test_unknown_state_rejected(rig):
    auth, _ = rig
    res = _fn(auth, "auth.oauth_enroll_complete")(state="not-a-real-state", code="c")
    assert res.ok is False and res.error == "invalid_or_expired_state"


def test_begin_requires_authenticated_context(rig):
    auth, _ = rig
    res = _fn(auth, "auth.oauth_enroll_begin")(provider_id=PROVIDER, connection_ref="c1")
    assert res.ok is False and res.error == "unauthenticated_context"


def test_unconfigured_provider_is_rejected(rig):
    auth, _ = rig
    res = _begin(auth, provider_id="microsoft", connection_ref="c1")  # seeded, empty client_id
    assert res.ok is False and res.error == "oauth_provider_not_configured"
