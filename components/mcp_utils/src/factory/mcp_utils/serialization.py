"""JSON serialization helpers for MCP tool results.

Shared by all bridge modules (api, dashboard, worker) to convert
non-JSON-serializable types returned by MCP tools into plain dicts.
"""

from __future__ import annotations

import datetime
import enum
from dataclasses import asdict, is_dataclass
from typing import Any


def make_serializable(obj: Any) -> Any:
    """Recursively convert non-JSON-serializable types to plain dicts.

    Handles: dataclasses, Pydantic models, enums, datetime, bytes,
    sets, frozensets, and nested combinations thereof.
    """
    if obj is None or isinstance(obj, (bool, int, float, str)):
        return obj
    if isinstance(obj, enum.Enum):
        return obj.value
    if isinstance(obj, (datetime.datetime, datetime.date)):
        return obj.isoformat()
    if isinstance(obj, bytes):
        return obj.decode("utf-8", errors="replace")
    if is_dataclass(obj) and not isinstance(obj, type):
        return make_serializable(asdict(obj))
    if hasattr(obj, "model_dump"):
        return make_serializable(obj.model_dump())
    if isinstance(obj, dict):
        return {str(k): make_serializable(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple, set, frozenset)):
        return [make_serializable(i) for i in obj]
    return str(obj)
