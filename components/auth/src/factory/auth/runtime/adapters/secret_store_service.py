"""SecretStorePort backed by the storage credential-slot service tools.

Reaches the hidden ``storage.credential_slot_*`` tools through the caller-bound
native invoker as caller ``auth`` with a ``credential_slot`` binding. Plaintext
secrets travel only on this in-process service-only path — never on a public MCP
surface. Any transport/authorization/decrypt failure collapses to ``None``.
"""
from __future__ import annotations

import hashlib
from typing import Any, Mapping

from factory.mcp_utils.interface import (
    get_envelope, get_service, protected_canonical_json,
)

from ..egress_models import SlotCoordinate
from ..egress_ports import SecretRead, SecretStorePort, SlotOutcome

_STORAGE = "storage"
_WRITE = "storage.credential_slot_write"
_READ = "storage.credential_slot_read"
_REVOKE = "storage.credential_slot_revoke"


class ServiceSecretStore(SecretStorePort):
    """Owner/tenant/provider/connection secret slots via the auth-only service path."""

    def __init__(self, invoker: Any | None = None) -> None:
        self._explicit = invoker

    def _caller(self) -> Any | None:
        invoker = self._explicit or get_service("tool_invoker_for_caller")
        if invoker is None:
            return None
        return invoker("auth")

    @staticmethod
    def _idem(op: str, slot: dict[str, Any]) -> str:
        return hashlib.sha256(protected_canonical_json({"op": op, "slot": slot})).hexdigest()

    def _invoke(self, tool: str, arguments: dict[str, Any], slot: dict[str, Any]) -> dict[str, Any] | None:
        native = self._caller()
        if native is None:
            return None
        try:
            result = native(
                {"brick_name": _STORAGE, "tool_name": tool},
                arguments=arguments, idempotency_key=self._idem(tool, slot),
                envelope=dict(get_envelope() or {}), credential_slot=slot,
            )
        except Exception:
            return None
        return _data(result)

    def write(self, coord: SlotCoordinate, secret: Mapping[str, Any], *,
              generation: int, expected_version: int | None) -> SlotOutcome | None:
        slot = coord.as_slot(generation)
        args: dict[str, Any] = {"slot": slot, "secret": dict(secret)}
        if expected_version is not None:
            args["expected_version"] = expected_version
        data = self._invoke(_WRITE, args, slot)
        return _outcome(data)

    def read(self, coord: SlotCoordinate, *, generation: int) -> SecretRead | None:
        slot = coord.as_slot(generation)
        data = self._invoke(_READ, {"slot": slot}, slot)
        if not data or not isinstance(data.get("secret"), dict):
            return None
        return SecretRead(
            secret=dict(data["secret"]), generation=int(data["generation"]),
            version=int(data["version"]))

    def revoke(self, coord: SlotCoordinate, *, generation: int) -> SlotOutcome | None:
        slot = coord.as_slot(generation)
        return _outcome(self._invoke(_REVOKE, {"slot": slot}, slot))


def _data(result: Any) -> dict[str, Any] | None:
    try:
        structured = result["result"]["structured_content"]
    except (KeyError, TypeError):
        return None
    if not isinstance(structured, dict) or structured.get("ok") is not True:
        return None
    data = structured.get("data")
    return data if isinstance(data, dict) else None


def _outcome(data: dict[str, Any] | None) -> SlotOutcome | None:
    if not data or "generation" not in data or "version" not in data:
        return None
    return SlotOutcome(generation=int(data["generation"]), version=int(data["version"]))


__all__ = ["ServiceSecretStore"]
