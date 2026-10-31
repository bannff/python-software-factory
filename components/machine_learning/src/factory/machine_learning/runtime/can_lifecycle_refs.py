"""Strict ML-owned references for CAN lifecycle authority boundaries."""
from __future__ import annotations

import re
from typing import Literal

from pydantic import BaseModel, ConfigDict, field_validator

from .can_legacy_binding import CanLegacyBinding


class _Frozen(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", strict=True)


class CanEvalsPointer(_Frozen):
    """Exact six-field pointer understood without importing Evals internals."""

    collection: Literal["eval_results"]
    doc_id: str
    record_kind: Literal["evaluation_run"]
    schema_version: Literal[2]
    revision: Literal["v2"]
    content_hash: str

    @field_validator("doc_id")
    @classmethod
    def _text(cls, value: str) -> str:
        if not value or value != value.strip():
            raise ValueError("Evals pointer text must be non-empty and trimmed")
        return value

    @field_validator("content_hash")
    @classmethod
    def _hash(cls, value: str) -> str:
        if re.fullmatch(r"sha256:[0-9a-f]{64}", value) is None:
            raise ValueError("Evals pointer content_hash must be SHA-256")
        return value


class CanTerminalRef(_Frozen):
    schema_version: Literal["1.0"] = "1.0"
    operation: str
    attempt_id: str
    request_sha256: str
    terminal_sha256: str

    @field_validator("operation")
    @classmethod
    def _operation(cls, value: str) -> str:
        if "@v1" not in value:
            raise ValueError("terminal operation identity must contain @v1")
        return value

    @field_validator("attempt_id")
    @classmethod
    def _attempt(cls, value: str) -> str:
        if re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}", value) is None:
            raise ValueError("terminal attempt identity is invalid")
        return value

    @field_validator("request_sha256", "terminal_sha256")
    @classmethod
    def _digest(cls, value: str) -> str:
        if re.fullmatch(r"[0-9a-f]{64}", value) is None:
            raise ValueError("terminal reference digest is invalid")
        return value


class CanConformanceReceiptRef(_Frozen):
    schema_version: Literal["1.0"] = "1.0"
    operation: str
    effect_id: str
    intent_sha256: str
    receipt_sha256: str

    @field_validator("operation")
    @classmethod
    def _operation(cls, value: str) -> str:
        if "@v1" not in value:
            raise ValueError("receipt operation identity must contain @v1")
        return value

    @field_validator("effect_id", "intent_sha256", "receipt_sha256")
    @classmethod
    def _digest(cls, value: str) -> str:
        if re.fullmatch(r"[0-9a-f]{64}", value) is None:
            raise ValueError("receipt reference digest is invalid")
        return value


__all__ = [
    "CanConformanceReceiptRef", "CanEvalsPointer", "CanLegacyBinding",
    "CanTerminalRef",
]
