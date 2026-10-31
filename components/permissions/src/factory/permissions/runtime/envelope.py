from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, Field, field_validator


_MAX_ATTRIBUTE_KEYS = 64
_MAX_KEY_LEN = 64
_MAX_STR_VAL_LEN = 512


class Envelope(BaseModel):
    tenant_id: str | None = None
    principal_id: str | None = None
    session_id: str | None = None

    request_id: str | None = None
    correlation_id: str | None = None

    agent_id: str | None = None
    tool_name: str | None = None

    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    attributes: dict[str, str | int | float | bool] = Field(default_factory=dict)

    @field_validator("attributes")
    @classmethod
    def _validate_attributes(
        cls, v: dict[str, str | int | float | bool]
    ) -> dict[str, str | int | float | bool]:
        if not isinstance(v, dict):
            raise ValueError("attributes must be a mapping")
        if len(v) > _MAX_ATTRIBUTE_KEYS:
            raise ValueError(f"attributes too large (max {_MAX_ATTRIBUTE_KEYS} keys)")

        out: dict[str, str | int | float | bool] = {}
        for k, val in v.items():
            if not isinstance(k, str):
                raise ValueError("attribute keys must be strings")
            if len(k) == 0 or len(k) > _MAX_KEY_LEN:
                raise ValueError(f"attribute key too long (max {_MAX_KEY_LEN})")

            if isinstance(val, str) and len(val) > _MAX_STR_VAL_LEN:
                raise ValueError(f"attribute '{k}' value too long (max {_MAX_STR_VAL_LEN})")
            if not isinstance(val, (str, int, float, bool)):
                raise ValueError(f"attribute '{k}' must be str|int|float|bool")
            out[k] = val
        return out


def parse_envelope(value: dict[str, Any] | None) -> Envelope:
    if value is None:
        return Envelope()
    if not isinstance(value, dict):
        raise ValueError("envelope must be a mapping")
    return Envelope.model_validate(value)


# Backwards-compatible alias
ContextEnvelope = Envelope
