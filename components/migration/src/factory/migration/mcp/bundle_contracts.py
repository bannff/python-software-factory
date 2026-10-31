"""Strict contracts for the companion-x-v1 bundle preview tool — kept
separate from ``PreviewInput``/``PreviewOutput`` (kirocrew-v1) rather than
overloading them, since a bundle preview has a genuinely different shape
(no staged directory files, no snapshot diagnostics, an extra
unsupported-kinds disclosure) and overloading would weaken the existing
kirocrew-v1 contract's literal-locked strictness for no benefit."""
from __future__ import annotations

from typing import Literal

from pydantic import Field, field_validator

from ..runtime.receipt_models import CommitStatus
from ..runtime.source_models import KindReport, PreviewSample
from .contracts import DTO

_BUNDLE_KINDS = Literal["memory", "lessons", "schedules"]


class BundlePreviewInput(DTO):
    source: Literal["companion-x-v1"] = "companion-x-v1"
    bundle_ref: str = Field(min_length=1, max_length=200)
    kinds: list[_BUNDLE_KINDS] | None = Field(default=None, max_length=5)

    @field_validator("kinds")
    @classmethod
    def _unique(cls, value: list[str] | None) -> list[str] | None:
        if value is not None and len(set(value)) != len(value):
            raise ValueError("migration bundle kinds must be unique")
        return value


class BundlePreviewOutput(DTO):
    source: Literal["companion-x-v1"] = "companion-x-v1"
    source_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    plan_digest: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    status: CommitStatus
    reports: tuple[KindReport, ...]
    samples: tuple[PreviewSample, ...] = Field(max_length=12)
    unsupported_kinds: tuple[str, ...] = Field(default=(), max_length=5)


__all__ = ["BundlePreviewInput", "BundlePreviewOutput"]
