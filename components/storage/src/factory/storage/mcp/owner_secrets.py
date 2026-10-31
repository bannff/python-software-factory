"""Public owner-secret MCP tools: list names, set, delete. No read tool.

Identity comes from the ambient envelope (tenant_id + principal_id), never
from tool input — accepting identity in the payload would let one caller
impersonate another owner's secret namespace. A missing/blank identity fails
closed rather than defaulting into a shared namespace (see OwnerSecretIdentity
in runtime/ports/owner_secrets.py).

Unlike the hidden, service-only credential_slots tools (registered directly in
server.py), these are registered through mcp/__init__.py so they are part of
the storage brick's normal public catalog — this is an owner-facing Settings
surface, not an internal broker seam.
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Any

from factory.mcp_utils.interface import (
    ToolResult, deterministic, fail, get_envelope, ok, operational,
)

from .contracts.owner_secrets import (
    OwnerSecretListInput, OwnerSecretListOutput, OwnerSecretReceiptOutput,
    OwnerSecretRefInput, OwnerSecretSetInput,
)

if TYPE_CHECKING:
    from ..runtime.runtime import StorageRuntime

_ERROR = "owner_secret_unavailable"


def _identity() -> Any:
    """Build the caller's OwnerSecretIdentity from the ambient envelope, or None."""
    from ..runtime.ports.owner_secrets import OwnerSecretError, OwnerSecretIdentity
    envelope = get_envelope() or {}
    try:
        return OwnerSecretIdentity(
            tenant_id=str(envelope.get("tenant_id") or ""),
            principal_id=str(envelope.get("principal_id") or ""),
        )
    except OwnerSecretError:
        return None


def register(mcp: Any, get_runtime: Any) -> None:
    """Register the public owner-secret list/set/delete tools."""

    @mcp.tool(name="storage.owner_secret_list")
    @deterministic(input_model=OwnerSecretListInput, output_model=OwnerSecretListOutput)
    def owner_secret_list() -> ToolResult[OwnerSecretListOutput]:
        """List the caller's own stored secret names. Values are never returned."""
        OwnerSecretListInput.model_validate({})
        ident = _identity()
        if ident is None:
            return fail(_ERROR)
        try:
            names = get_runtime().get_owner_secret_store().list_names(ident)
            return ok(OwnerSecretListOutput(names=names))
        except Exception:
            return fail(_ERROR)

    @mcp.tool(name="storage.owner_secret_set")
    @operational(input_model=OwnerSecretSetInput, output_model=OwnerSecretReceiptOutput,
                 idempotent=False)
    def owner_secret_set(name: str, value: str) -> ToolResult[OwnerSecretReceiptOutput]:
        """Create or overwrite the caller's secret at ``name`` (last-write-wins)."""
        parsed = OwnerSecretSetInput.model_validate({"name": name, "value": value})
        ident = _identity()
        if ident is None:
            return fail(_ERROR)
        try:
            get_runtime().get_owner_secret_store().set_secret(ident, parsed.name, parsed.value)
            return ok(OwnerSecretReceiptOutput(name=parsed.name, ok=True))
        except Exception:
            return fail(_ERROR)

    @mcp.tool(name="storage.owner_secret_delete")
    @operational(input_model=OwnerSecretRefInput, output_model=OwnerSecretReceiptOutput,
                 idempotent=True)
    def owner_secret_delete(name: str) -> ToolResult[OwnerSecretReceiptOutput]:
        """Remove the caller's secret at ``name``. No-op (ok=False) if absent."""
        parsed = OwnerSecretRefInput.model_validate({"name": name})
        ident = _identity()
        if ident is None:
            return fail(_ERROR)
        try:
            existed = get_runtime().get_owner_secret_store().delete_secret(ident, parsed.name)
            return ok(OwnerSecretReceiptOutput(name=parsed.name, ok=existed))
        except Exception:
            return fail(_ERROR)


__all__ = ["register"]
