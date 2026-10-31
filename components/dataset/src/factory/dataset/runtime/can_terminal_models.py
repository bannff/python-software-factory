"""Frozen contracts for the Dataset CAN materialization terminal."""
from __future__ import annotations

import hashlib
import json
import re
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, StrictInt, field_validator, model_validator

from .dbc_models import MessageFingerprint
from .failure_pattern_models import FailurePatternRef


class _Frozen(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class CanTerminalRequest(_Frozen):
    """Dataset-owned inputs formerly embedded in can_run_full_pipeline."""

    attempt_id: str
    mf4_dir: str
    dbc_path: str | None = None
    dbc_catalog_id: str = ""
    dbc_catalog_version: str = ""
    vehicle_alias: str = ""
    vehicle_make: str = ""
    vehicle_model: str = ""
    vehicle_year: StrictInt | None = Field(default=None, ge=1886, le=3000)
    message_fingerprints: tuple[MessageFingerprint, ...] = ()
    failure_pattern_refs: tuple[FailurePatternRef, ...] = ()
    vehicle_id: str = "unknown"
    max_samples: int = Field(default=20_000, gt=0)
    config_overrides: dict[str, dict[str, Any]] = Field(default_factory=dict)
    use_context: bool = False
    context_sources: tuple[str, ...] = ()
    emit_timespans: bool = False
    schema_version: Literal["1.0"] = "1.0"

    @field_validator("attempt_id", "mf4_dir", "vehicle_id")
    @classmethod
    def _text(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("CAN terminal text inputs must be non-empty")
        return value

    @field_validator("dbc_path")
    @classmethod
    def _optional_path(cls, value: str | None) -> str | None:
        if value is not None and not value.strip():
            raise ValueError("dbc_path cannot be blank")
        return value

    @field_validator("attempt_id")
    @classmethod
    def _attempt_id(cls, value: str) -> str:
        if re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}", value) is None:
            raise ValueError("attempt_id must be safe ASCII and at most 128 characters")
        return value

    @field_validator("context_sources", mode="before")
    @classmethod
    def _sources(cls, value: Any) -> tuple[str, ...]:
        return tuple(value or ())

    @model_validator(mode="after")
    def _context(self) -> "CanTerminalRequest":
        if self.use_context and not self.context_sources:
            raise ValueError("use_context=True requires context_sources")
        synthesize = self.config_overrides.get("synthesize") or {}
        forbidden = {"scania_data_uri", "scania_model_id"}.intersection(synthesize)
        if forbidden:
            raise ValueError("CAN terminal synthesize overrides cannot invoke ML training")
        path_keys = _external_path_keys(self.config_overrides)
        if path_keys:
            raise ValueError(
                f"CAN terminal overrides cannot reference external paths: {path_keys[0]}"
            )
        return self


class CanAttemptRecord(_Frozen):
    """Self-digested pointer for one explicit workflow attempt."""

    schema_version: Literal["1.0"] = "1.0"
    attempt_id: str
    request_sha256: str
    state: Literal[
        "claimed", "materializing", "publishing", "succeeded", "failed"
    ]
    terminal_uri: str | None = None
    terminal_sha256: str | None = None
    record_sha256: str

    @field_validator("request_sha256", "terminal_sha256", "record_sha256")
    @classmethod
    def _digest(cls, value: str | None) -> str | None:
        if value is not None and (
            len(value) != 64 or any(c not in "0123456789abcdef" for c in value)
        ):
            raise ValueError("attempt digests must be lowercase SHA-256")
        return value

    @model_validator(mode="after")
    def _terminal_pointer(self) -> "CanAttemptRecord":
        terminal = self.state in {"succeeded", "failed"}
        if terminal != bool(self.terminal_uri and self.terminal_sha256):
            raise ValueError("terminal attempt state and pointer disagree")
        if self.record_sha256 != attempt_record_digest(self):
            raise ValueError("attempt record digest mismatch")
        return self


def _external_path_keys(value: Any, prefix: str = "") -> list[str]:
    found: list[str] = []
    if isinstance(value, dict):
        for key, item in value.items():
            name = f"{prefix}.{key}" if prefix else str(key)
            if str(key).lower().endswith(("_path", "_uri", "_file", "_filename")):
                found.append(name)
            found.extend(_external_path_keys(item, name))
    elif isinstance(value, (list, tuple)):
        for index, item in enumerate(value):
            found.extend(_external_path_keys(item, f"{prefix}[{index}]"))
    return sorted(found)


def attempt_record_digest(record: CanAttemptRecord | dict[str, Any]) -> str:
    values = record.model_dump(mode="json") if isinstance(record, BaseModel) else dict(record)
    values.pop("record_sha256", None)
    content = json.dumps(
        values, sort_keys=True, separators=(",", ":"), ensure_ascii=False,
        allow_nan=False,
    ).encode()
    return hashlib.sha256(content).hexdigest()


def make_attempt_record(**values: Any) -> CanAttemptRecord:
    values.setdefault("schema_version", "1.0")
    values["record_sha256"] = "0" * 64
    values["record_sha256"] = attempt_record_digest(values)
    return CanAttemptRecord.model_validate(values)


__all__ = [
    "CanAttemptRecord", "CanTerminalRequest", "attempt_record_digest",
    "make_attempt_record",
]
