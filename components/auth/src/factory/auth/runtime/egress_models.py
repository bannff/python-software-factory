"""Strict, provider-neutral models for tokenless credential-injecting egress.

Callers supply NONE of URL / method / headers / scopes / token endpoint — only a
provider id, route id, opaque connection ref, and a typed payload. The route
manifest (immutable registry data) supplies the fixed HTTPS origin, method,
path template, required scopes, allowed payload fields, and byte/time limits.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, JsonValue, field_validator

from factory.mcp_utils.interface import egress_request_digest as request_digest

JsonObject = dict[str, JsonValue]
_REF = re.compile(r"^[A-Za-z0-9_.:-]{1,128}$")
_DIGEST = re.compile(r"^[0-9a-f]{64}$")
SlotKind = Literal["client_secret", "refresh_token"]
_SECRET_KEYS = frozenset({
    "access_token", "refresh_token", "id_token", "token", "tokens", "secret",
    "secrets", "client_secret", "authorization", "api_key", "apikey",
    "private_key", "password", "bearer", "credential", "credentials",
})


def redact_secrets(value: Any) -> Any:
    """Drop any secret/token-named field from a provider result (defense-in-depth).

    Even though the fake providers never echo a token, a future real provider
    adapter might; this guarantees such a field can never reach a caller.
    """
    if isinstance(value, dict):
        return {k: redact_secrets(v) for k, v in value.items()
                if not (isinstance(k, str) and k.strip().lower() in _SECRET_KEYS)}
    if isinstance(value, list):
        return [redact_secrets(v) for v in value]
    return value


@dataclass(frozen=True, slots=True)
class SlotCoordinate:
    """Auth-side slot coordinate (mirrors storage SlotIdentity across MCP)."""
    tenant_id: str
    owner_id: str
    provider_id: str
    connection_ref: str
    slot_kind: SlotKind

    def as_slot(self, generation: int) -> dict[str, object]:
        return {
            "tenant_id": self.tenant_id, "owner_id": self.owner_id,
            "provider_id": self.provider_id, "connection_ref": self.connection_ref,
            "slot_kind": self.slot_kind, "generation": generation,
        }


_MAX_STR = 8192
FieldType = Literal["str", "int", "bool"]


@dataclass(frozen=True, slots=True)
class ProviderRoute:
    """Immutable route manifest: the only source of URL/method/scope authority."""
    provider_id: str
    route_id: str
    origin: str            # fixed https origin
    method: str            # GET/POST/...
    path_template: str
    required_scopes: tuple[str, ...]
    allowed_fields: frozenset[str]
    secret_slot_kind: SlotKind
    request_schema: tuple[tuple[str, FieldType], ...] = ()
    max_bytes: int = 65_536
    timeout_s: int = 10
    redirect_policy: Literal["none"] = "none"

    def __post_init__(self) -> None:
        if not self.origin.startswith("https://"):
            raise ValueError("provider route origin must be https")
        if self.method not in ("GET", "POST", "PUT", "PATCH", "DELETE"):
            raise ValueError("provider route method is not allowed")
        if not {name for name, _ in self.request_schema} <= self.allowed_fields:
            raise ValueError("request_schema declares a field outside allowed_fields")

    def validate_payload(self, payload: dict[str, Any]) -> bool:
        """Reject unknown keys and any value whose type/length violates the schema."""
        if not set(payload).issubset(self.allowed_fields):
            return False
        types = {"str": str, "int": int, "bool": bool}
        for name, kind in self.request_schema:
            if name not in payload:
                continue
            value = payload[name]
            # bool is an int subclass — reject the cross-type confusion explicitly
            if kind != "bool" and isinstance(value, bool):
                return False
            if not isinstance(value, types[kind]):
                return False
            if kind == "str" and len(value) > _MAX_STR:
                return False
        return True


class EgressRequest(BaseModel):
    """Public egress request — carries no URL/method/header/scope/token."""
    model_config = ConfigDict(extra="forbid", strict=True)
    provider_id: str = Field(min_length=1, max_length=128)
    route_id: str = Field(min_length=1, max_length=128)
    connection_ref: str = Field(min_length=1, max_length=128)
    payload: JsonObject = Field(default_factory=dict)
    request_digest: str

    @field_validator("connection_ref")
    @classmethod
    def _ref(cls, value: str) -> str:
        if not _REF.fullmatch(value):
            raise ValueError("connection_ref must be opaque")
        return value

    @field_validator("request_digest")
    @classmethod
    def _digest(cls, value: str) -> str:
        if not _DIGEST.fullmatch(value):
            raise ValueError("request_digest must be a sha256 hex digest")
        return value


class EgressResult(BaseModel):
    """Sanitized business result — never a token, secret, or provider header."""
    model_config = ConfigDict(extra="forbid", strict=True)
    status: Literal["ok", "unauthorized", "denied"]
    result: JsonObject = Field(default_factory=dict)


__all__ = [
    "EgressRequest", "EgressResult", "FieldType", "ProviderRoute",
    "SlotCoordinate", "SlotKind", "redact_secrets", "request_digest",
]
