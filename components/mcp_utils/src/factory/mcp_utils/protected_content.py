"""Domain-neutral protected-content contracts, keys, and sanitation."""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import re
from datetime import datetime, timezone
from typing import Any, Literal, Protocol
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, field_validator

_REF = re.compile(r"^pc_v1_[A-Za-z0-9_-]{22}$")
_DIGEST = re.compile(r"^[0-9a-f]{64}$")
_SENSITIVE = frozenset({
    "attachment", "attachments", "bcc", "body", "cc", "content", "html",
    "message", "payload", "provider_request", "provider_response", "query",
    "raw", "raw_evidence", "recipient", "recipients", "subject", "text", "to",
})
_PROTECTED_ERROR_FIELD = re.compile(
    r"(?i)\b(" + "|".join(sorted(_SENSITIVE)) + r")\s*([:=])\s*(?:\"[^\"]*\"|'[^']*'|[^,;}\]\n]+)"
)


def canonical_json(value: Any) -> bytes:
    """Encode a JSON-only value deterministically for fingerprints and AEAD."""
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False).encode("utf-8")


class ProtectedContentDescriptor(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)
    classification: str = Field(min_length=1, max_length=64)
    purpose: str = Field(min_length=1, max_length=128)
    tenant_id: str = Field(min_length=1, max_length=128)
    owner_principal_id: str = Field(min_length=1, max_length=128)
    artifact_kind: str = Field(min_length=1, max_length=128)
    schema_version: Literal["v1"] = "v1"
    profile_version: Literal["local-v1"] = "local-v1"
    retention_until: datetime | None = None
    projection_profile: Literal["metadata", "email-summary"] = "metadata"


class ProtectedArtifactRef(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)
    artifact_ref: str
    fingerprint: str
    descriptor: ProtectedContentDescriptor

    @field_validator("artifact_ref")
    @classmethod
    def _ref(cls, value: str) -> str:
        if not _REF.fullmatch(value):
            raise ValueError("invalid protected artifact reference")
        return value

    @field_validator("fingerprint")
    @classmethod
    def _fingerprint(cls, value: str) -> str:
        if not _DIGEST.fullmatch(value):
            raise ValueError("invalid protected artifact fingerprint")
        return value


class ProtectedContentProjection(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)
    artifact_ref: str
    fingerprint: str
    values: dict[str, str | int | bool | None]


class ProtectedContentPolicyProfile(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)
    profile_version: Literal["local-v1"] = "local-v1"
    allowed_projection_profiles: frozenset[Literal["metadata", "email-summary"]] = frozenset({"metadata", "email-summary"})
    encryption_required: Literal[True] = True


class AuthorizationAssertion(BaseModel):
    """Trusted, envelope-derived authorization input; never tool-derived."""
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)
    principal_id: str = Field(min_length=1, max_length=128)
    tenant_id: str = Field(min_length=1, max_length=128)
    action: str = Field(min_length=1, max_length=64)
    purpose: str = Field(min_length=1, max_length=128)
    expires_at: datetime | None = None

    def permits(self, descriptor: ProtectedContentDescriptor, action: str, purpose: str) -> bool:
        return (self.principal_id == descriptor.owner_principal_id and self.tenant_id == descriptor.tenant_id
                and self.action == action and self.purpose == purpose
                and (self.expires_at is None or self.expires_at >= datetime.now(timezone.utc)))


class ProtectedContentKeyProvider(Protocol):
    def active(self) -> tuple[str, bytes]: ...
    def resolve(self, key_id: str) -> bytes: ...
    def index_key(self, tenant_id: str) -> bytes: ...


class LocalEnvironmentKeyProvider:
    """Fail-closed configured key provider; key id is deployment configuration."""
    def __init__(self, key_id: str = "local-v1", environ: dict[str, str] | None = None) -> None:
        self._key_id, self._environ = key_id, environ if environ is not None else os.environ

    def _key_for(self, encoded: str | None) -> bytes:
        try:
            key = base64.b64decode(encoded or "", validate=True)
        except Exception as exc:
            raise ValueError("protected key unavailable") from exc
        if len(key) != 32: raise ValueError("protected key unavailable")
        return key

    def _key(self) -> bytes:
        return self._key_for(self._environ.get("FACTORY_PROTECTED_CONTENT_LOCAL_KEK"))

    def _historical(self) -> dict[str, str]:
        try:
            values = json.loads(self._environ.get("FACTORY_PROTECTED_CONTENT_LOCAL_HISTORICAL_KEKS", "{}"))
            return values if isinstance(values, dict) and all(isinstance(k, str) and isinstance(v, str) for k, v in values.items()) else {}
        except json.JSONDecodeError as exc:
            raise ValueError("protected key unavailable") from exc

    def active(self) -> tuple[str, bytes]: return self._key_id, self._key()
    def resolve(self, key_id: str) -> bytes:
        return self._key() if key_id == self._key_id else self._key_for(self._historical().get(key_id))
    def index_key(self, tenant_id: str) -> bytes:
        root = self._key_for(
            self._environ.get("FACTORY_PROTECTED_CONTENT_LOCAL_INDEX_KEY"),
        )
        return hmac.digest(root, b"protected-index-v1:" + tenant_id.encode(), "sha256")


class TestKeyProvider:
    """Explicit test-only rotating key provider, never selected from request data."""
    __test__ = False
    def __init__(self, key: bytes = b"k" * 32, key_id: str = "test-v1") -> None:
        if len(key) != 32: raise ValueError("test key must be 32 bytes")
        self._keys, self._active, self._index_root = {key_id: key}, key_id, hashlib.sha256(key + b"index").digest()
    def rotate(self, key_id: str, key: bytes) -> None:
        if len(key) != 32: raise ValueError("test key must be 32 bytes")
        self._keys[key_id], self._active = key, key_id
    def active(self) -> tuple[str, bytes]: return self._active, self._keys[self._active]
    def resolve(self, key_id: str) -> bytes: return self._keys[key_id]
    def index_key(self, tenant_id: str) -> bytes: return hmac.digest(self._index_root, tenant_id.encode(), "sha256")


def new_artifact_ref() -> str:
    return "pc_v1_" + base64.urlsafe_b64encode(uuid4().bytes).decode().rstrip("=")


def sanitize_protected(value: Any, *, reject: bool = False) -> Any:
    """Recursively redact protected values; reject persistence ingress when asked."""
    if isinstance(value, BaseModel): value = value.model_dump(mode="json")
    if isinstance(value, dict):
        output: dict[str, Any] = {}
        for key, item in value.items():
            if key.lower() in _SENSITIVE:
                if reject: raise ValueError("protected inline content is forbidden")
                output[key] = "[protected]"
            else:
                output[key] = sanitize_protected(item, reject=reject)
        return output
    if isinstance(value, list): return [sanitize_protected(item, reject=reject) for item in value]
    return value


def sanitize_protected_error(error: str) -> str:
    """Redact protected field values while retaining ordinary error semantics."""
    return _PROTECTED_ERROR_FIELD.sub(r"\1\2[protected]", error)


def sanitize_protected_error_value(value: Any) -> Any:
    """Recursively redact error payloads before they cross durable or event boundaries."""
    if isinstance(value, str):
        return sanitize_protected_error(value)
    if isinstance(value, dict):
        return {key: ("[protected]" if key.lower() in _SENSITIVE
                      else sanitize_protected_error_value(item))
                for key, item in value.items()}
    if isinstance(value, list):
        return [sanitize_protected_error_value(item) for item in value]
    return value


def _reject_or_walk(value: Any, reject: bool) -> Any:
    if reject: raise ValueError("protected inline content is forbidden")
    return sanitize_protected(value, reject=False)
