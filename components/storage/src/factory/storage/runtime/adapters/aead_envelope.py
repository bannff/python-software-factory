"""Shared AES-256-GCM DEK/KEK envelope codec (per-call AAD builder callback).

Generalizes the identical seal/open loop already duplicated in
``credential_slots_codec.SlotCodec`` and ``protected_sqlite``'s inline codec:
same ``{v,key_id,payload_nonce,ciphertext,wrap_nonce,wrapped_dek}`` envelope,
same AES-256-GCM DEK wrapped by the active KEK. The only per-store variance was
the AAD dict, so this codec takes an ``AadBuilder`` callback — given the
``key_id`` the codec resolves internally, it returns the AAD bytes to bind
this seal/open to. Callers build their own AAD (binding whatever identity
fields matter to them) via ``protected_canonical_json``; key resolution stays
encapsulated inside the codec.

New code (``owner_secrets``) uses this codec. ``SlotCodec`` and the
``protected_sqlite`` inline codec are NOT retrofitted onto it in this change —
both are security-sensitive with existing test coverage; that retrofit is a
follow-up, not bundled with unrelated new functionality.
"""
from __future__ import annotations

import base64
import json
import os
import re
from typing import Any, Callable

from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from factory.mcp_utils.interface import ProtectedContentKeyProvider, protected_canonical_json

_KEY_ID = re.compile(r"^[A-Za-z0-9_.-]{1,128}$")
_B64URL = re.compile(r"^[A-Za-z0-9_-]+$")
_FIELDS = frozenset({"v", "key_id", "payload_nonce", "ciphertext", "wrap_nonce", "wrapped_dek"})
AadBuilder = Callable[[str], bytes]
"""Given the resolved ``key_id``, return the AAD bytes to bind this seal/open to."""


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


class AeadEnvelopeCodec:
    """Seal/open opaque JSON payloads under the active/resolved KEK."""

    def __init__(self, keys: ProtectedContentKeyProvider) -> None:
        self._keys = keys

    def seal(self, aad_builder: AadBuilder, payload: dict[str, Any]) -> str:
        """Encrypt ``payload`` under a fresh DEK, wrapped by the active KEK.

        Resolves the active ``key_id`` internally (key resolution stays
        encapsulated) and hands it to ``aad_builder`` so the caller's AAD can
        bind the same ``key_id`` the envelope will carry.
        """
        key_id, kek = self._keys.active()
        if not _KEY_ID.fullmatch(key_id) or len(kek) != 32:
            raise ValueError("invalid active key")
        aad = aad_builder(key_id)
        dek, pn, wn = AESGCM.generate_key(256), os.urandom(12), os.urandom(12)
        return json.dumps({
            "v": "1", "key_id": key_id, "payload_nonce": _enc(pn),
            "ciphertext": _enc(AESGCM(dek).encrypt(pn, protected_canonical_json(payload), aad)),
            "wrap_nonce": _enc(wn), "wrapped_dek": _enc(AESGCM(kek).encrypt(wn, dek, aad)),
        }, separators=(",", ":"))

    def open(self, aad_builder: AadBuilder, raw: str) -> dict[str, Any]:
        """Decrypt an envelope sealed with the same AAD; raises on any mismatch."""
        env = json.loads(raw)
        if not isinstance(env, dict) or set(env) != _FIELDS or env.get("v") != "1":
            raise ValueError("invalid envelope")
        key_id = env["key_id"]
        if not isinstance(key_id, str) or not _KEY_ID.fullmatch(key_id):
            raise ValueError("invalid envelope")
        aad = aad_builder(key_id)
        dek = AESGCM(self._keys.resolve(key_id)).decrypt(
            _dec(env["wrap_nonce"], exact=12), _dec(env["wrapped_dek"], minimum=48), aad)
        if len(dek) != 32:
            raise ValueError("invalid envelope")
        result = json.loads(AESGCM(dek).decrypt(
            _dec(env["payload_nonce"], exact=12), _dec(env["ciphertext"], minimum=16), aad))
        if not isinstance(result, dict):
            raise ValueError("invalid payload")
        return result


__all__ = ["AeadEnvelopeCodec"]
