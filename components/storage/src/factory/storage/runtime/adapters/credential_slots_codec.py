"""AES-256-GCM envelope codec for credential slots (AAD-bound to slot identity).

Reuses the DEK-wrap envelope shape and ``ProtectedContentKeyProvider`` from
mcp_utils. The AAD binds the full slot identity plus generation, version, and
key_id, so a sealed record cannot be replayed under a different identity,
generation, or version.
"""
from __future__ import annotations

import base64
import json
import os
import re
from typing import Any, Mapping

from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from factory.mcp_utils.interface import (
    ProtectedContentKeyProvider, protected_canonical_json,
)

from ..ports.credential_slots import SlotIdentity

_KEY_ID = re.compile(r"^[A-Za-z0-9_.-]{1,128}$")
_B64URL = re.compile(r"^[A-Za-z0-9_-]+$")
_FIELDS = frozenset({"v", "key_id", "payload_nonce", "ciphertext", "wrap_nonce", "wrapped_dek"})


def _enc(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).decode().rstrip("=")


def _dec(value: Any, *, exact: int | None = None, minimum: int = 1) -> bytes:
    if not isinstance(value, str) or not _B64URL.fullmatch(value) or len(value) > 16384:
        raise ValueError("invalid envelope")
    decoded = base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))
    if _enc(decoded) != value or len(decoded) < minimum \
            or (exact is not None and len(decoded) != exact):
        raise ValueError("invalid envelope")
    return decoded


class SlotCodec:
    """Seal/open a slot secret under the active/resolved KEK with identity AAD."""

    def __init__(self, keys: ProtectedContentKeyProvider) -> None:
        self._keys = keys

    @staticmethod
    def _aad(ident: SlotIdentity, generation: int, version: int, key_id: str) -> bytes:
        return protected_canonical_json({
            "v": "cred-slot-1", "tenant_id": ident.tenant_id, "owner_id": ident.owner_id,
            "provider_id": ident.provider_id, "connection_ref": ident.connection_ref,
            "slot_kind": ident.slot_kind, "generation": generation,
            "version": version, "key_id": key_id,
        })

    def seal(self, ident: SlotIdentity, generation: int, version: int,
             secret: Mapping[str, Any]) -> str:
        key_id, kek = self._keys.active()
        if not _KEY_ID.fullmatch(key_id) or len(kek) != 32:
            raise ValueError("invalid active key")
        dek, pn, wn = AESGCM.generate_key(256), os.urandom(12), os.urandom(12)
        aad = self._aad(ident, generation, version, key_id)
        return json.dumps({
            "v": "1", "key_id": key_id, "payload_nonce": _enc(pn),
            "ciphertext": _enc(AESGCM(dek).encrypt(pn, protected_canonical_json(dict(secret)), aad)),
            "wrap_nonce": _enc(wn), "wrapped_dek": _enc(AESGCM(kek).encrypt(wn, dek, aad)),
        }, separators=(",", ":"))

    def open(self, ident: SlotIdentity, generation: int, version: int, raw: str) -> dict[str, Any]:
        env = json.loads(raw)
        if not isinstance(env, dict) or set(env) != _FIELDS or env.get("v") != "1":
            raise ValueError("invalid envelope")
        key_id = env["key_id"]
        if not isinstance(key_id, str) or not _KEY_ID.fullmatch(key_id):
            raise ValueError("invalid envelope")
        aad = self._aad(ident, generation, version, key_id)
        dek = AESGCM(self._keys.resolve(key_id)).decrypt(
            _dec(env["wrap_nonce"], exact=12), _dec(env["wrapped_dek"], minimum=48), aad)
        if len(dek) != 32:
            raise ValueError("invalid envelope")
        result = json.loads(AESGCM(dek).decrypt(
            _dec(env["payload_nonce"], exact=12), _dec(env["ciphertext"], minimum=16), aad))
        if not isinstance(result, dict):
            raise ValueError("invalid payload")
        return result


__all__ = ["SlotCodec"]
