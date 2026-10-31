"""Frozen stdlib-only canonical JSON and signable-message builders for dcal/v1."""
from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from datetime import datetime
from typing import Any, Final

MAX_BYTES = 1 << 20
MAX_DEPTH = 16
MAX_COLLECTION = 256
MAX_STRING_BYTES = 64 << 10
DCAL_DOMAIN_TAGS: Final[frozenset[str]] = frozenset({"idempotency", "record", "signature"})
_TIMESTAMP = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{6}Z$")


def parse_canonical_json(value: str | bytes) -> Any:
    """Parse bounded UTF-8 JSON, rejecting duplicate keys and non-integer numbers."""
    if isinstance(value, bytes):
        if len(value) > MAX_BYTES:
            raise ValueError("raw JSON exceeds 1 MiB")
        try:
            value = value.decode("utf-8", "strict")
        except UnicodeDecodeError as exc:
            raise ValueError("JSON must be strict UTF-8") from exc
    if not isinstance(value, str):
        raise TypeError("JSON input must be text or bytes")
    if len(value.encode("utf-8")) > MAX_BYTES:
        raise ValueError("raw JSON exceeds 1 MiB")
    try:
        parsed = json.loads(value, object_pairs_hook=_pairs, parse_float=_reject_float,
                            parse_constant=_reject_constant)
    except (json.JSONDecodeError, ValueError) as exc:
        raise ValueError("invalid dcal/v1 JSON") from exc
    return _normalize(parsed, depth=1)


def parse_rfc3339_utc_microseconds(value: str) -> datetime:
    """Accept only RFC3339 UTC timestamps with six fractional digits and terminal Z."""
    if not isinstance(value, str) or _TIMESTAMP.fullmatch(value) is None:
        raise ValueError("timestamp must be RFC3339 UTC with six fractional digits and Z")
    try:
        return datetime.strptime(value, "%Y-%m-%dT%H:%M:%S.%fZ")
    except ValueError as exc:
        raise ValueError("invalid RFC3339 UTC timestamp") from exc


def canonical_json_text(value: Any) -> str:
    """Normalize strings to NFC, then emit compact UTF-8 lexical-key JSON."""
    normalized = _normalize(value, depth=1)
    text = _emit(normalized)
    if len(text.encode("utf-8")) > MAX_BYTES:
        raise ValueError("canonical JSON exceeds 1 MiB")
    return text


def canonical_json_bytes(value: Any) -> bytes:
    return canonical_json_text(value).encode("utf-8")


def sha256_domain(tag: str, payload: bytes) -> str:
    """Hash bytes with an allowlisted dcal/v1 purpose tag."""
    if tag not in DCAL_DOMAIN_TAGS:
        raise ValueError("unknown DCAL domain tag")
    if not isinstance(payload, bytes):
        raise TypeError("digest payload must be bytes")
    return hashlib.sha256(b"dcal/v1/" + tag.encode("ascii") + b"\x00" + payload).hexdigest()


def canonical_digest(value: Any, *, domain_tag: str) -> str:
    return sha256_domain(domain_tag, canonical_json_bytes(value))


def build_signable_message(
    *, purpose: str, tenant_id: str, ledger_id: str, policy_digest: str, canonical_digest: str,
) -> bytes:
    """Build the exact, purpose-limited dcal/v1 signature payload."""
    if purpose not in DCAL_DOMAIN_TAGS:
        raise ValueError("unknown DCAL signing purpose")
    return canonical_json_bytes({
        "canonical_digest": canonical_digest, "ledger_id": ledger_id,
        "policy_digest": policy_digest, "profile": "dcal", "protocol": "dcal",
        "purpose": purpose, "tenant_id": tenant_id, "version": "v1",
    })


def _pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, item in pairs:
        if key in result:
            raise ValueError("duplicate JSON key")
        result[key] = item
    return result


def _reject_float(_: str) -> None:
    raise ValueError("floating-point values are forbidden")


def _reject_constant(_: str) -> None:
    raise ValueError("non-finite numeric constants are forbidden")


def _normalize(value: Any, *, depth: int) -> Any:
    if depth > MAX_DEPTH:
        raise ValueError("JSON depth exceeds 16")
    if value is None or isinstance(value, bool):
        return value
    if type(value) is int:
        return value
    if isinstance(value, str):
        normalized = unicodedata.normalize("NFC", value)
        if len(normalized.encode("utf-8")) > MAX_STRING_BYTES:
            raise ValueError("JSON string exceeds 64 KiB")
        return normalized
    if isinstance(value, list):
        if len(value) > MAX_COLLECTION:
            raise ValueError("JSON collection exceeds 256 items")
        return [_normalize(item, depth=depth + 1) for item in value]
    if isinstance(value, dict):
        if len(value) > MAX_COLLECTION:
            raise ValueError("JSON object exceeds 256 keys")
        result: dict[str, Any] = {}
        for key, item in value.items():
            if not isinstance(key, str):
                raise TypeError("JSON object keys must be strings")
            normalized_key = _normalize(key, depth=depth + 1)
            if normalized_key in result:
                raise ValueError("duplicate keys after NFC normalization")
            result[normalized_key] = _normalize(item, depth=depth + 1)
        return result
    raise TypeError("only JSON null, booleans, integers, strings, arrays, and objects are allowed")


def _emit(value: Any) -> str:
    if value is None: return "null"
    if value is True: return "true"
    if value is False: return "false"
    if type(value) is int: return str(value)
    if isinstance(value, str): return json.dumps(value, ensure_ascii=False, separators=(",", ":"))
    if isinstance(value, list): return "[" + ",".join(_emit(item) for item in value) + "]"
    return "{" + ",".join(_emit(key) + ":" + _emit(value[key]) for key in sorted(value, key=lambda key: key.encode("utf-8"))) + "}"


__all__ = ["DCAL_DOMAIN_TAGS", "MAX_BYTES", "MAX_COLLECTION", "MAX_DEPTH", "MAX_STRING_BYTES", "build_signable_message", "canonical_digest", "canonical_json_bytes", "canonical_json_text", "parse_canonical_json", "parse_rfc3339_utc_microseconds", "sha256_domain"]
