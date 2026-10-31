"""Strict immutable primitives for execution manifests."""
from __future__ import annotations

import re
from typing import Any

from pydantic import BaseModel, ConfigDict, JsonValue, field_validator

_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


class FrozenModel(BaseModel):
    """Data-only manifest model with closed, strict fields."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)


class DigestValue(FrozenModel):
    algorithm: str = "sha256"
    value: str

    @field_validator("value")
    @classmethod
    def _sha256(cls, value: str) -> str:
        if not _SHA256_RE.fullmatch(value):
            raise ValueError("digest must be lowercase SHA-256")
        return value


JsonObject = dict[str, JsonValue]


def json_object(value: dict[str, Any]) -> JsonObject:
    """Return a JSON-only deep copy or fail closed."""
    import json

    return json.loads(json.dumps(
        value, sort_keys=True, separators=(",", ":"),
        ensure_ascii=False, allow_nan=False,
    ))


__all__ = ["DigestValue", "FrozenModel", "JsonObject", "json_object"]
