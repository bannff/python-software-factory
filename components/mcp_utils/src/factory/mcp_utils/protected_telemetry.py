"""Safe telemetry attribute projections for direct recording APIs."""
from __future__ import annotations

from typing import Any

from pydantic import BaseModel

from .protected_fields import (
    EXCEPTION_FIELDS as _EXCEPTION_KEYS,
    field_name as _field_name,
    sensitive_key as _sensitive_key,
)


def telemetry_attributes(value: Any) -> dict[str, Any]:
    """Keep safe attributes, replace protected aliases, and drop exception text."""
    plain = value.model_dump(mode="json") if isinstance(value, BaseModel) else value

    def project(item: Any) -> Any:
        if isinstance(item, dict):
            output: dict[str, Any] = {}
            for key, nested in item.items():
                field = _field_name(key)
                if _sensitive_key(key):
                    output[key] = "[protected]"
                elif field in _EXCEPTION_KEYS:
                    continue
                else:
                    output[key] = project(nested)
            return output
        if isinstance(item, (list, tuple)):
            return [project(nested) for nested in item]
        if type(item) in (str, int, float, bool) or item is None:
            return item[:120] if isinstance(item, str) else item
        return None

    projected = project(plain)
    return projected if isinstance(projected, dict) else {}
