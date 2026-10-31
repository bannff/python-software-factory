"""Framework-neutral contracts for one-round confirmation elicitation."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable, Literal, Mapping, Protocol, TypeAlias

from pydantic import BaseModel

_MAX_MESSAGE_LENGTH = 4096
_MAX_SCHEMA_BYTES = 16384
_MAX_RESPONSE_BYTES = 16384
_MAX_FIELDS = 32
_KEY = re.compile(r"^[A-Za-z0-9_-]{1,64}$")
_LONG_SENSITIVE = (
    "password", "passphrase", "passcode", "secret", "token", "credential",
    "apikey", "privatekey", "authorizationcode", "verificationcode",
    "recoverycode", "sessioncookie", "securityanswer",
)
_SHORT_SENSITIVE = frozenset({"otp", "totp", "hotp", "pin", "bearer", "jwt", "mfa", "csrf"})
_ALLOWED_TYPES = {"boolean", "string"}
_MAX_ENUM_OPTIONS = 8


def _sensitive_name(name: str) -> bool:
    separated = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", name)
    normalized = re.sub(r"[^A-Za-z0-9]+", "_", separated).lower().strip("_")
    parts = set(normalized.split("_"))
    compact = normalized.replace("_", "")
    return bool(parts & _SHORT_SENSITIVE) or any(
        term in compact for term in _LONG_SENSITIVE
    ) or any(compact.startswith(term) for term in _SHORT_SENSITIVE)


def _validate_property_schema(schema: Any) -> None:
    """Enforce MCP form elicitation's flat primitive-schema subset."""
    if not isinstance(schema, dict) or "$ref" in schema or "properties" in schema:
        raise ValueError("elicitation fields must be flat primitive schemas")
    field_format = str(schema.get("format", "")).casefold()
    if field_format in {"password", "secret"}:
        raise ValueError("form elicitation cannot collect sensitive fields")
    if "anyOf" in schema:
        choices = [item for item in schema["anyOf"] if item.get("type") != "null"]
        if len(choices) != 1:
            raise ValueError("elicitation nullable fields require one primitive type")
        _validate_property_schema(choices[0])
        return
    field_type = schema.get("type")
    if field_type not in _ALLOWED_TYPES:
        raise ValueError("elicitation confirmation fields must be boolean or a string enum")
    if field_type == "string":
        options = schema.get("enum")
        if not isinstance(options, list) or not 2 <= len(options) <= _MAX_ENUM_OPTIONS:
            raise ValueError("elicitation string fields must be a 2..8 option enum")
        if not all(isinstance(option, str) and option for option in options):
            raise ValueError("elicitation enum options must be non-empty strings")


def _validate_form_schema(schema: dict[str, Any], properties: dict[str, Any]) -> None:
    required = schema.get("required", [])
    if not isinstance(required, list) or not set(required).issubset(properties):
        raise ValueError("elicitation required fields must name declared properties")
    if any(_sensitive_name(name) for name in properties):
        raise ValueError("form elicitation cannot collect sensitive fields")
    for field_schema in properties.values():
        _validate_property_schema(field_schema)


@dataclass(frozen=True, slots=True)
class ElicitationForm:
    """A bounded boolean-confirmation or string-enum-choice form presented to an elicitation handler."""

    message: str
    requested_schema: dict[str, Any]

    def __post_init__(self) -> None:
        if not self.message or len(self.message) > _MAX_MESSAGE_LENGTH:
            raise ValueError("elicitation message must contain 1..4096 characters")
        properties = self.requested_schema.get("properties")
        if self.requested_schema.get("type") != "object" or not isinstance(properties, dict):
            raise ValueError("elicitation response schema must describe an object")
        if not 1 <= len(properties) <= _MAX_FIELDS:
            raise ValueError("elicitation form must contain 1..32 fields")
        _validate_form_schema(self.requested_schema, properties)
        if len(json.dumps(self.requested_schema, separators=(",", ":")).encode()) > _MAX_SCHEMA_BYTES:
            raise ValueError("elicitation response schema exceeds 16384 bytes")


@dataclass(frozen=True, slots=True)
class ElicitationFormRequest:
    """One keyed confirmation whose content is validated by a strict model."""

    message: str
    response_model: type[BaseModel]
    key: str = "elicitation"
    form: ElicitationForm = field(init=False)

    def __post_init__(self) -> None:
        if not _KEY.fullmatch(self.key):
            raise ValueError("elicitation key must match [A-Za-z0-9_-]{1,64}")
        config = self.response_model.model_config
        if config.get("extra") != "forbid" or config.get("strict") is not True:
            raise ValueError("elicitation response model must be strict and forbid extra fields")
        schema = self.response_model.model_json_schema(mode="validation")
        if schema.get("additionalProperties") is not False:
            raise ValueError("elicitation response schema must deny additional properties")
        object.__setattr__(self, "form", ElicitationForm(self.message, schema))


@dataclass(frozen=True, slots=True)
class ElicitationResponse:
    """Neutral accept, decline, or cancel response."""

    action: Literal["accept", "decline", "cancel"]
    content: Mapping[str, Any] | None = None

    def __post_init__(self) -> None:
        if self.action == "accept" and self.content is None:
            raise ValueError("accepted elicitation requires content")
        if self.action != "accept" and self.content is not None:
            raise ValueError("declined or cancelled elicitation cannot carry content")
        if self.content is not None:
            try:
                size = len(json.dumps(
                    dict(self.content), separators=(",", ":"), allow_nan=False,
                ).encode())
            except (TypeError, ValueError) as exc:
                raise ValueError("elicitation content must be JSON-safe") from exc
            if size > _MAX_RESPONSE_BYTES:
                raise ValueError("elicitation content exceeds 16384 bytes")


@dataclass(frozen=True, slots=True)
class PrepareNeedsElicitation:
    """Preparation cannot finish until one form is answered."""

    request: ElicitationFormRequest


@dataclass(frozen=True, slots=True)
class PrepareReady:
    """Preparation completed with arguments for the terminal handler."""

    arguments: Mapping[str, Any]
    protected: bool = True


PrepareResult: TypeAlias = PrepareNeedsElicitation | PrepareReady
PrepareCallable: TypeAlias = Callable[
    [Mapping[str, Any], ElicitationResponse | None],
    PrepareResult | Awaitable[PrepareResult],
]
ElicitationHandler: TypeAlias = Callable[
    [ElicitationForm], ElicitationResponse | Awaitable[ElicitationResponse]
]


class SideEffectFreePrepare(Protocol):
    """Side-effect-free preparation callable; effects belong to the terminal handler."""

    def __call__(
        self,
        validated_arguments: Mapping[str, Any],
        response: ElicitationResponse | None,
    ) -> PrepareResult | Awaitable[PrepareResult]: ...


__all__ = [
    "ElicitationForm", "ElicitationFormRequest", "ElicitationHandler",
    "ElicitationResponse", "PrepareCallable", "PrepareNeedsElicitation",
    "PrepareReady", "PrepareResult", "SideEffectFreePrepare",
]
