"""Public vendor-neutral email tools backed by the tokenless egress rail.

These are the agent-facing capability: an agent (or a Companion-X persona) calls
``communications.provider_email_send`` / ``_list`` with a provider id + opaque
connection ref + business fields. The adapter delegates to the hidden
``auth.credentialed_egress`` tool; the agent never sees a token, a scope, a URL,
or a credential slot. Distinct from the artifact-based ``communications.send_email``
(that sends pre-stored protected content via an injected client); this path is
the provider-account, broker-injected-token capability.
"""
from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from factory.mcp_utils.interface import (
    ToolResult, fail, get_envelope, get_principal_id, ok, operational,
)
from factory.mcp_utils.registration import typed_tool

from factory.integrations.runtime.adapters.egress_email import EgressEmailAdapter


class _In(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class ProviderEmailSendInput(_In):
    provider_id: str = Field(min_length=1, max_length=128)
    connection_ref: str = Field(min_length=1, max_length=128)
    subject: str = Field(min_length=1, max_length=998)
    body: str = Field(min_length=1, max_length=65_536)
    to: str = Field(min_length=1, max_length=320)


class ProviderEmailListInput(_In):
    provider_id: str = Field(min_length=1, max_length=128)
    connection_ref: str = Field(min_length=1, max_length=128)
    top: int = Field(default=10, ge=1, le=100)
    query: str = Field(default="", max_length=512)


class ProviderEmailOutput(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    status: str
    result: dict[str, Any] = {}


def _identity() -> tuple[str, str] | None:
    envelope, owner_id = get_envelope() or {}, get_principal_id()
    tenant_id = envelope.get("tenant_id")
    if not isinstance(owner_id, str) or not owner_id \
            or not isinstance(tenant_id, str) or not tenant_id:
        return None
    return owner_id, tenant_id


def register(mcp: Any, runtime: Any) -> None:
    """Register the vendor-neutral provider email tools."""
    adapter = EgressEmailAdapter()

    @typed_tool(mcp, name="communications.provider_email_send")
    @operational(input_model=ProviderEmailSendInput, output_model=ProviderEmailOutput)
    def provider_email_send(provider_id: str, connection_ref: str, subject: str,
                            body: str, to: str) -> ToolResult[ProviderEmailOutput]:
        who = _identity()
        if who is None:
            return fail("unauthenticated_context")
        try:
            out = adapter.send_email(
                provider_id=provider_id, connection_ref=connection_ref,
                subject=subject, body=body, to=to,
                principal_id=who[0], tenant_id=who[1])
        except Exception:
            return fail("email_egress_denied")
        return ok(ProviderEmailOutput(status=out["status"], result=out["result"]))

    @typed_tool(mcp, name="communications.provider_email_list")
    @operational(input_model=ProviderEmailListInput, output_model=ProviderEmailOutput)
    def provider_email_list(provider_id: str, connection_ref: str,
                            top: int = 10, query: str = "") -> ToolResult[ProviderEmailOutput]:
        who = _identity()
        if who is None:
            return fail("unauthenticated_context")
        try:
            out = adapter.list_messages(
                provider_id=provider_id, connection_ref=connection_ref,
                top=top, query=query, principal_id=who[0], tenant_id=who[1])
        except Exception:
            return fail("email_egress_denied")
        return ok(ProviderEmailOutput(status=out["status"], result=out["result"]))


__all__ = ["register"]
