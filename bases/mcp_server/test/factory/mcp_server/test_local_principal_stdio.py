"""Transport-aware local principal for trusted stdio/in-process transports.

Over stdio there is no HTTP bearer context, so principal() would return None and
is_authorized would deny every tool. In local mode the controller falls back to
a server-owned principal (still policy-evaluated); in production it stays None.
"""

from __future__ import annotations

import mcp.server.auth.middleware.auth_context as auth_context

from factory.mcp_server.runtime.access_control import (
    GatewayAccessController, _local_principal,
)


class _DummyDecisionPoint:
    def decide(self, **_: object) -> dict[str, object]:
        return {"decision": "allow", "reason": "ok"}


def test_local_principal_returned_when_no_bearer(monkeypatch) -> None:
    monkeypatch.setattr(auth_context, "get_access_token", lambda: None)
    controller = GatewayAccessController(_DummyDecisionPoint(), local_principal=_local_principal())
    principal = controller.principal()
    assert principal is not None
    assert principal.subject == "svc:local"
    assert "operator" in principal.roles


def test_no_principal_without_token_in_production(monkeypatch) -> None:
    monkeypatch.setattr(auth_context, "get_access_token", lambda: None)
    controller = GatewayAccessController(_DummyDecisionPoint(), local_principal=None)
    assert controller.principal() is None


def test_local_principal_is_server_owned_not_caller_derived() -> None:
    """Identity is fixed server-side, never from caller input."""
    principal = _local_principal()
    assert principal.subject == "svc:local"
    assert principal.client_id == "local-stdio"
    assert principal.scopes == ()
