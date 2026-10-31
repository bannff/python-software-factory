"""Frozen durable contracts for ML-owned CAN lifecycle attempts."""
from __future__ import annotations

import hashlib
import re
from typing import Any, Literal, TypeVar

from pydantic import BaseModel, ConfigDict, field_validator, model_validator

from .can_lifecycle_canonical import canonical_json


class _Frozen(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


_FrozenT = TypeVar("_FrozenT", bound=_Frozen)


class CanLifecycleAttempt(_Frozen):
    schema_version: Literal["1.0"] = "1.0"
    operation: str
    attempt_id: str
    request_sha256: str
    state: Literal["claimed", "running", "succeeded", "failed"]
    terminal_uri: str | None = None
    terminal_sha256: str | None = None
    record_sha256: str

    @field_validator("operation", "attempt_id")
    @classmethod
    def _safe_identity(cls, value: str) -> str:
        if re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._:@-]{0,159}", value) is None:
            raise ValueError("lifecycle identities must be safe bounded ASCII")
        return value

    @field_validator("request_sha256", "terminal_sha256", "record_sha256")
    @classmethod
    def _digest(cls, value: str | None) -> str | None:
        if value is not None and re.fullmatch(r"[0-9a-f]{64}", value) is None:
            raise ValueError("lifecycle digests must be lowercase SHA-256")
        return value

    @model_validator(mode="after")
    def _integrity(self) -> "CanLifecycleAttempt":
        terminal = self.state in {"succeeded", "failed"}
        if terminal != bool(self.terminal_uri and self.terminal_sha256):
            raise ValueError("attempt terminal pointer and state disagree")
        if self.record_sha256 != record_digest(self.model_dump(mode="json")):
            raise ValueError("attempt record digest mismatch")
        return self


class CanEffectIntent(_Frozen):
    schema_version: Literal["1.0"] = "1.0"
    operation: str
    effect_id: str
    request_sha256: str
    unit: str
    inputs: dict[str, Any]
    intent_sha256: str

    @model_validator(mode="after")
    def _integrity(self) -> "CanEffectIntent":
        values = self.model_dump(mode="json")
        observed = values.pop("intent_sha256")
        if observed != hashlib.sha256(canonical_json(values)).hexdigest():
            raise ValueError("effect intent digest mismatch")
        return self


class CanEffectReceipt(_Frozen):
    schema_version: Literal["1.0"] = "1.0"
    effect_id: str
    intent_sha256: str
    output: dict[str, Any]
    receipt_sha256: str

    @model_validator(mode="after")
    def _integrity(self) -> "CanEffectReceipt":
        values = self.model_dump(mode="json")
        observed = values.pop("receipt_sha256")
        if observed != hashlib.sha256(canonical_json(values)).hexdigest():
            raise ValueError("effect receipt digest mismatch")
        return self


def record_digest(values: dict[str, Any]) -> str:
    body = dict(values)
    body.pop("record_sha256", None)
    return hashlib.sha256(canonical_json(body)).hexdigest()


def with_digest(model: type[_FrozenT], **values: Any) -> _FrozenT:
    field = next(key for key in values if key.endswith("_sha256") and values[key] == "")
    body = dict(values)
    body[field] = hashlib.sha256(canonical_json({
        key: value for key, value in body.items() if key != field
    })).hexdigest()
    return model.model_validate(body)


__all__ = [
    "CanEffectIntent", "CanEffectReceipt", "CanLifecycleAttempt",
    "record_digest", "with_digest",
]
