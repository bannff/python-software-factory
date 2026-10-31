"""Vendor-neutral email egress via the tokenless credential rail.

Delegates to auth's hidden ``auth.credentialed_egress`` tool as caller
``integrations`` (mirrors ``mcp_protected_artifacts.MCPProtectedArtifactMaterializer``).
Integrations never sees a token and never touches a credential slot — it passes
only provider/route ids, a typed payload, and a request digest computed with the
SHARED ``mcp_utils.egress_request_digest`` (so it never imports auth internals).
The sanitized business result comes back; a token could never be in it.
"""
from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict

from factory.mcp_utils.interface import egress_request_digest, get_service


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class _EgressData(_Strict):
    status: Literal["ok", "unauthorized", "denied"]
    result: dict[str, Any]


class _ToolResult(_Strict):
    schema_version: Literal["v1"]
    ok: bool
    data: _EgressData | None = None
    error: str | None = None
    idempotency_key: str | None = None


class _NativeToolResult(_Strict):
    kind: Literal["tool"]
    structured_content: _ToolResult
    content: list[Any]
    meta: dict[str, Any]


class _NativeEnvelope(_Strict):
    ok: bool
    result: _NativeToolResult | None = None
    error: Any = None
    idempotency_key: str | None = None


class EgressEmailAdapter:
    """One adapter implementing both send (EmailSender-style) and mailbox read."""

    def _invoker(self) -> Any:
        factory = get_service("tool_invoker_for_caller")
        if not callable(factory):
            raise ValueError("email egress unavailable")
        invoker = factory("integrations")
        if not callable(invoker):
            raise ValueError("email egress unavailable")
        return invoker

    def _egress(self, provider_id: str, route_id: str, connection_ref: str,
                payload: dict[str, Any], principal_id: str, tenant_id: str) -> dict[str, Any]:
        digest = egress_request_digest(provider_id, route_id, connection_ref, payload)
        request = {"provider_id": provider_id, "route_id": route_id,
                   "connection_ref": connection_ref, "payload": payload,
                   "request_digest": digest}
        binding = {"provider_id": provider_id, "route_id": route_id,
                   "connection_ref": connection_ref, "request_digest": digest}
        raw = self._invoker()(
            {"brick_name": "auth", "tool_name": "auth.credentialed_egress"},
            arguments={"request": request}, credential_egress=binding,
            idempotency_key=f"egress:{digest}",
            envelope={"principal_id": principal_id, "tenant_id": tenant_id})
        env = _NativeEnvelope.model_validate(raw)
        if not env.ok or env.result is None or not env.result.structured_content.ok \
                or env.result.structured_content.data is None:
            raise ValueError("email egress denied")
        data = env.result.structured_content.data
        return {"status": data.status, "result": data.result}

    def send_email(self, *, provider_id: str, connection_ref: str, subject: str,
                   body: str, to: str, principal_id: str, tenant_id: str) -> dict[str, Any]:
        return self._egress(provider_id, "send_mail", connection_ref,
                            {"subject": subject, "body": body, "to": to},
                            principal_id, tenant_id)

    def list_messages(self, *, provider_id: str, connection_ref: str, top: int,
                      query: str, principal_id: str, tenant_id: str) -> dict[str, Any]:
        payload: dict[str, Any] = {"top": top}
        if query:
            payload["filter"] = query
        return self._egress(provider_id, "list_messages", connection_ref,
                            payload, principal_id, tenant_id)


__all__ = ["EgressEmailAdapter"]
