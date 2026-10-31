"""Central schema-version dispatcher for Pydantic models at the trust boundary.

Every Pydantic model at a tool boundary carries an explicit ``schema_version``
field. When old-shape payloads arrive (older caller, stale cache, replayed
event), they fail ``model_validate`` until a migration step reshapes them
forward. This dispatcher walks the chain. New writes default to the latest
version.

Registration pattern (for callers):

    from factory.mcp_utils.runtime.schema_migration import register_step

    def _v1_to_v2(data: dict) -> dict:
        return {**data, "schema_version": "v2", "content": data.pop("body")}

    register_step("KbIngestRequest", "v1", _v1_to_v2)
"""

from __future__ import annotations

from threading import RLock
from typing import Callable

from pydantic import BaseModel, ValidationError

_STEP: dict[tuple[str, str], Callable[[dict], dict]] = {}
_LOCK = RLock()


class SchemaMigrationError(ValueError):
    """Raised when no migration path exists from the incoming version."""


def register_step(
    model_name: str, from_version: str, step: Callable[[dict], dict]
) -> None:
    """Register a migration step (thread-safe; last write wins)."""
    with _LOCK:
        _STEP[(model_name, from_version)] = step


def clear_steps() -> None:
    """Clear all registered steps (tests only)."""
    with _LOCK:
        _STEP.clear()


def _current_version(model: type[BaseModel]) -> str:
    """Read the default schema_version from the model, else ``v1``."""
    field = model.model_fields.get("schema_version")
    if field is None:
        return "v1"
    default = field.default
    return default if isinstance(default, str) else "v1"


def _step_for(
    model_name: str, current_version: str
) -> Callable[[dict], dict] | None:
    with _LOCK:
        return _STEP.get((model_name, current_version))


def migrate_to(data: dict, target: type[BaseModel]) -> BaseModel:
    """Walk ``data`` forward through registered steps until it fits ``target``.

    Missing ``schema_version`` first attempts current-shape validation (flat
    kwargs from modern callers). On failure it defaults to ``v1`` and walks
    registered migration steps (legacy payloads).
    """
    payload = dict(data)
    model_name = target.__name__
    latest = _current_version(target)
    if "schema_version" not in payload:
        try:
            return target.model_validate(payload)
        except ValidationError:
            current = "v1"
    else:
        current = payload["schema_version"]
        if not isinstance(current, str):
            raise SchemaMigrationError("schema_version must be a string")
    safety = 0
    while current != latest:
        if safety > 100:
            raise SchemaMigrationError(
                f"Too many migration steps for {model_name} (possible cycle)"
            )
        step = _step_for(model_name, current)
        if step is None:
            raise SchemaMigrationError(
                f"No migration path from {current} to {latest} for {model_name}"
            )
        payload = step(payload)
        if not isinstance(payload, dict):
            raise SchemaMigrationError(
                f"{model_name} migration step from {current} returned "
                f"{type(payload).__name__}, expected dict"
            )
        current = payload.get("schema_version", current)
        safety += 1
    try:
        return target.model_validate(payload)
    except ValidationError as exc:
        raise SchemaMigrationError(
            f"{model_name} validation failed at latest ({latest}): {exc}"
        ) from exc


__all__ = [
    "SchemaMigrationError",
    "clear_steps",
    "migrate_to",
    "register_step",
]
