"""Strict typed boundary for recording a neutral Finding."""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class FindingSubject(_Strict):
    type: str = Field(default="", max_length=64)
    id: str = Field(default="", max_length=1024)
    location: str = Field(default="", max_length=1024)


class FindingTaxonomyRef(_Strict):
    scheme: str = Field(min_length=1, max_length=64)
    id: str = Field(min_length=1, max_length=128)
    label: str = Field(default="", max_length=256)


class RecordFindingInput(_Strict):
    title: str = Field(min_length=1, max_length=300)
    severity: Literal["critical", "high", "medium", "low", "info"]
    kind: str = Field(default="other", min_length=1, max_length=64)
    category: str = Field(default="", max_length=128)
    description: str = Field(default="", max_length=8000)
    evidence: str = Field(default="", max_length=8000)
    remediation: str = Field(default="", max_length=8000)
    subject: FindingSubject | None = None
    taxonomy: list[FindingTaxonomyRef] = Field(default_factory=list, max_length=32)
    run_id: str = Field(default="", max_length=256)
    app: str = Field(default="", max_length=256)
    backend: str = ""


class RecordFindingOutput(_Strict):
    finding_id: str
    state: str
    available: list[str] | None = None
    error: str | None = None
