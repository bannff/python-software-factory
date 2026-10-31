"""Validation and bounded evidence primitives for SDK-native tool chaos."""
from __future__ import annotations

import math
from typing import Any

from .adapters.tool_catalog import TOOL_NAMES

MAX_CASES = 8
MAX_FAULTS = 4
MAX_TOOLS = 3
MAX_STATE_CACHE = 8
MAX_DEPTH = 4
MAX_ITEMS = 16
MAX_STRING = 512

_EFFECTS = {
    "timeout": ("Timeout", {"error_message"}),
    "network_error": ("NetworkError", {"error_message"}),
    "execution_error": ("ExecutionError", {"error_message"}),
    "validation_error": ("ValidationError", {"error_message"}),
    "truncate_fields": ("TruncateFields", {"max_length"}),
    "remove_fields": ("RemoveFields", {"remove_ratio"}),
    "corrupt_values": ("CorruptValues", {"corrupt_ratio"}),
}


def selected_tools(tool_names: list[str]) -> tuple[str, ...]:
    """Require a bounded, unique subset of the developer-owned catalog."""
    if not tool_names or len(tool_names) > MAX_TOOLS or len(set(tool_names)) != len(tool_names):
        raise ValueError("tool_names must be a nonempty unique allowlisted subset")
    unknown = set(tool_names) - set(TOOL_NAMES)
    if unknown:
        raise ValueError(f"unknown tool names: {sorted(unknown)}")
    return tuple(tool_names)


def validate_cases(cases: list[dict[str, Any]]) -> None:
    """Keep execution variants and prompt payloads bounded."""
    if not cases or len(cases) > MAX_CASES or not all(isinstance(case, dict) for case in cases):
        raise ValueError(f"cases must contain between 1 and {MAX_CASES} objects")
    for case in cases:
        if not isinstance(case.get("input", ""), (str, dict)) or not isinstance(case.get("metadata", {}), dict):
            raise ValueError("case input must be a string or object and metadata must be an object")
        text = case.get("input", "")
        if len(text if isinstance(text, str) else str(text)) > 4096:
            raise ValueError("case input exceeds 4096 characters")


def _native_effect(raw: dict[str, Any]) -> Any:
    from strands_evals import chaos
    effect_type = raw.get("effect_type")
    if effect_type not in _EFFECTS:
        raise ValueError(f"unsupported native effect: {effect_type!r}")
    class_name, allowed = _EFFECTS[effect_type]
    if set(raw) - (allowed | {"effect_type"}):
        raise ValueError(f"unsupported parameters for {effect_type}")
    if len(str(raw.get("error_message", ""))) > 256:
        raise ValueError("effect error_message exceeds 256 characters")
    max_length = raw.get("max_length")
    if max_length is not None:
        try:
            parsed_max_length = int(max_length)
        except (TypeError, ValueError) as exc:
            raise ValueError("truncate_fields max_length must be an integer") from exc
        if parsed_max_length > MAX_STRING:
            raise ValueError(f"truncate_fields max_length exceeds {MAX_STRING}")
    try:
        return getattr(chaos, class_name)(**{key: raw[key] for key in allowed if key in raw})
    except (TypeError, ValueError) as exc:
        raise ValueError(f"invalid {effect_type} effect: {exc}") from exc


def fault_conditions(faults: list[dict[str, Any]], tools: tuple[str, ...]) -> list[dict[str, Any]]:
    """Translate bounded declarative faults to native SDK effect instances."""
    if not faults or len(faults) > MAX_FAULTS:
        raise ValueError(f"faults must contain between 1 and {MAX_FAULTS} entries")
    conditions: set[str] = set()
    result: list[dict[str, Any]] = []
    for raw in faults:
        if not isinstance(raw, dict) or set(raw) - {"condition", "tool_effects"}:
            raise ValueError("fault configuration contains unsupported fields")
        condition = raw.get("condition")
        effects = raw.get("tool_effects")
        if not isinstance(condition, str) or not condition or condition == "baseline" or len(condition) > 64:
            raise ValueError("fault condition must be a unique non-baseline string")
        if condition in conditions or not isinstance(effects, dict) or not effects:
            raise ValueError("fault condition and tool_effects must be nonempty and unique")
        native: dict[str, list[Any]] = {}
        for name, effect_specs in effects.items():
            if name not in tools or not isinstance(effect_specs, list) or len(effect_specs) != 1:
                raise ValueError("each selected tool may have exactly one native effect")
            if not isinstance(effect_specs[0], dict):
                raise ValueError("effect specification must be an object")
            native[name] = [_native_effect(effect_specs[0])]
        conditions.add(condition)
        result.append({"condition": condition, "effects": {"tool_effects": native}})
    return result


def bounded_value(value: Any, depth: int = 0) -> Any:
    """Produce recursively bounded JSON-safe state evidence."""
    if depth >= MAX_DEPTH:
        return "<depth-truncated>"
    if hasattr(value, "model_dump"):
        return bounded_value(value.model_dump(mode="json"), depth + 1)
    if isinstance(value, dict):
        return {
            str(key)[:64]: bounded_value(item, depth + 1)
            for key, item in list(value.items())[:MAX_ITEMS]
        }
    if isinstance(value, (list, tuple)):
        return [bounded_value(item, depth + 1) for item in value[:MAX_ITEMS]]
    if isinstance(value, str):
        return value[:MAX_STRING]
    if isinstance(value, float) and not math.isfinite(value):
        return str(value)
    return value if value is None or isinstance(value, (bool, int, float)) else str(value)[:MAX_STRING]
