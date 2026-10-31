"""Service-only credential-slot MCP tools — callable only by the auth broker.

Hidden tools (registered directly in server.py, excluded from mcp/__init__).
Storage is a pure data plane: it stores/returns encrypted-at-rest secret bytes
by exact identity + generation. Tenant/owner authorization is the auth broker's
concern; storage enforces only the service-only caller handshake, the generation
fence, and the AAD-bound envelope. Every failure returns one opaque error.
"""
from __future__ import annotations

from typing import Any, Callable, TYPE_CHECKING

from factory.mcp_utils.interface import (
    ToolResult, fail, ok, operational, service_only,
)

from .contracts.credential_slots import (
    CredentialSlotReadOutput, CredentialSlotReceiptOutput, CredentialSlotRefInput,
    CredentialSlotWriteInput, SlotRef,
)

if TYPE_CHECKING:
    from ..runtime.runtime import StorageRuntime

_ERROR = "credential_slot_unavailable"


def _identity(slot: SlotRef) -> Any:
    from ..runtime.ports.credential_slots import SlotIdentity
    return SlotIdentity(
        tenant_id=slot.tenant_id, owner_id=slot.owner_id,
        provider_id=slot.provider_id, connection_ref=slot.connection_ref,
        slot_kind=slot.slot_kind,
    )


def register(mcp: Any, get_runtime: Callable[[], "StorageRuntime"]) -> None:
    """Register the hidden auth-only credential-slot surface."""

    @mcp.tool(name="storage.credential_slot_write")
    @service_only(callers={"auth"}, binding="credential_slot")
    @operational(input_model=CredentialSlotWriteInput,
                 output_model=CredentialSlotReceiptOutput, idempotent=False)
    def write(slot: dict[str, Any], secret: dict[str, Any],
              expected_version: int | None = None) -> ToolResult[CredentialSlotReceiptOutput]:
        try:
            ref = SlotRef.model_validate(slot)
            receipt = get_runtime().get_credential_slot_store().write(
                _identity(ref), secret, generation=ref.generation,
                expected_version=expected_version,
            )
            return ok(CredentialSlotReceiptOutput(
                generation=receipt.generation, version=receipt.version))
        except Exception:
            return fail(_ERROR)

    @mcp.tool(name="storage.credential_slot_read")
    @service_only(callers={"auth"}, binding="credential_slot")
    @operational(input_model=CredentialSlotRefInput,
                 output_model=CredentialSlotReadOutput, idempotent=False)
    def read(slot: dict[str, Any]) -> ToolResult[CredentialSlotReadOutput]:
        try:
            ref = SlotRef.model_validate(slot)
            decrypted = get_runtime().get_credential_slot_store().read(
                _identity(ref), generation=ref.generation)
            return ok(CredentialSlotReadOutput(
                secret=decrypted.secret, generation=decrypted.generation,
                version=decrypted.version))
        except Exception:
            return fail(_ERROR)

    @mcp.tool(name="storage.credential_slot_revoke")
    @service_only(callers={"auth"}, binding="credential_slot")
    @operational(input_model=CredentialSlotRefInput,
                 output_model=CredentialSlotReceiptOutput, idempotent=False)
    def revoke(slot: dict[str, Any]) -> ToolResult[CredentialSlotReceiptOutput]:
        try:
            ref = SlotRef.model_validate(slot)
            receipt = get_runtime().get_credential_slot_store().revoke(
                _identity(ref), generation=ref.generation)
            return ok(CredentialSlotReceiptOutput(
                generation=receipt.generation, version=receipt.version))
        except Exception:
            return fail(_ERROR)

    @mcp.tool(name="storage.credential_slot_rekey")
    @service_only(callers={"auth"}, binding="credential_slot")
    @operational(input_model=CredentialSlotRefInput,
                 output_model=CredentialSlotReceiptOutput, idempotent=False)
    def rekey(slot: dict[str, Any]) -> ToolResult[CredentialSlotReceiptOutput]:
        try:
            ref = SlotRef.model_validate(slot)
            receipt = get_runtime().get_credential_slot_store().rekey(
                _identity(ref), generation=ref.generation)
            return ok(CredentialSlotReceiptOutput(
                generation=receipt.generation, version=receipt.version))
        except Exception:
            return fail(_ERROR)


__all__ = ["register"]
