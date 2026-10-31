"""Operational MCP tools - stateful but idempotent operations."""
from __future__ import annotations

from typing import Any
from factory.mcp_utils.interface import ToolResult, fail, get_envelope, get_principal_id, ok, operational
from factory.mcp_utils.registration import typed_tool
from factory.integrations.mcp.email_contracts import SendEmailInput, SendEmailOutput
from factory.integrations.runtime.email_models import EmailIdempotencyConflict, ProviderReceiptError
from factory.integrations.runtime.runtime import IntegrationsRuntime


def register(mcp: Any, runtime: IntegrationsRuntime) -> None:
    """Register operational tools."""
    @typed_tool(mcp, name="communications.send_email")
    @operational(input_model=SendEmailInput, output_model=SendEmailOutput)
    def communications_send_email(connection_ref: str, artifact: dict[str, Any], idempotency_key: str) -> ToolResult[SendEmailOutput]:
        """Materialize one owner-bound artifact in memory and send it once."""
        envelope, owner_id = get_envelope() or {}, get_principal_id()
        tenant_id = envelope.get("tenant_id")
        if not isinstance(owner_id, str) or not isinstance(tenant_id, str): return fail("unauthenticated_context")
        request = SendEmailInput(connection_ref=connection_ref, artifact=artifact, idempotency_key=idempotency_key)
        try:
            receipt = runtime.send_protected_email(owner_id, tenant_id, request)
        except ProviderReceiptError: return fail("email_provider_receipt_invalid")
        except ValueError: return fail("protected_artifact_unavailable")
        except Exception: return fail("email_provider_failed")
        if receipt is None: return fail("email_connection_unavailable")
        if isinstance(receipt, EmailIdempotencyConflict): return fail("email_idempotency_conflict", idempotency_key=idempotency_key)
        return ok(SendEmailOutput.model_validate(receipt.model_dump()), idempotency_key=idempotency_key)

    @mcp.tool()
    @operational
    def integrations_connect(connector_id: str) -> dict[str, Any]:
        success = runtime.connect(connector_id); connector = runtime.get(connector_id)
        return {"connector_id": connector_id, "connected": success, "status": connector.status if connector else "not_found"}

    @mcp.tool()
    @operational
    def integrations_disconnect(connector_id: str) -> dict[str, Any]:
        return {"connector_id": connector_id, "disconnected": runtime.disconnect(connector_id)}

    @mcp.tool()
    @operational
    def integrations_call(connector_id: str, method: str, path: str = "", params: dict[str, Any] | None = None, data: Any = None, headers: dict[str, str] | None = None) -> dict[str, Any]:
        """Reject generic connector effects until a trusted context is available."""
        envelope, principal_id = get_envelope() or {}, get_principal_id()
        if not isinstance(principal_id, str) or not isinstance(envelope.get("tenant_id"), str):
            return {"success": False, "error": "unauthenticated_context", "connector_id": connector_id}
        result = runtime.call(
            connector_id=connector_id, method=method, path=path,
            params=params, data=data, headers=headers,
        )
        return {
            "success": result.success, "status_code": result.status_code,
            "latency_ms": result.latency_ms, "connector_id": result.connector_id,
        }
