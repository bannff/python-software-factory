"""Safe, typed structured-output models for registered agent graphs."""
from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class ResearchPlan(BaseModel):
    objective: str
    tracks: list[str] = Field(min_length=4)
    acceptance_criteria: list[str] = Field(default_factory=list)
    model_config = ConfigDict(extra="forbid")


class EvidenceItem(BaseModel):
    claim: str
    source: str
    relevance: str
    model_config = ConfigDict(extra="forbid")


class ResearchEvidence(BaseModel):
    track: str
    findings: list[EvidenceItem] = Field(min_length=1)
    limitations: list[str] = Field(default_factory=list)
    complete: bool
    model_config = ConfigDict(extra="forbid")


class ResearchDraft(BaseModel):
    title: str
    summary: str
    sections: list[str] = Field(min_length=1)
    sources: list[str] = Field(min_length=1)
    model_config = ConfigDict(extra="forbid")


class LoopCycleReport(BaseModel):
    disposition: str = Field(pattern=r"^(continue|success|blocked)$")
    summary: str = Field(min_length=1, max_length=32_768)
    blocker: str | None = Field(default=None, max_length=16_384)
    evidence: list[str] = Field(default_factory=list, max_length=64)
    model_config = ConfigDict(extra="forbid")


_SCHEMAS: dict[str, type[BaseModel]] = {
    "research-plan-v1": ResearchPlan,
    "research-evidence-v1": ResearchEvidence,
    "research-draft-v1": ResearchDraft,
    "loop-cycle-report-v1": LoopCycleReport,
}


def resolve_output_schema(name: str | None) -> type[BaseModel] | None:
    """Resolve a closed registry name; import paths are never accepted."""
    if name is None:
        return None
    try:
        return _SCHEMAS[name]
    except KeyError as exc:
        raise ValueError(f"Unknown structured output schema: {name!r}") from exc


__all__ = [
    "EvidenceItem", "LoopCycleReport", "ResearchDraft", "ResearchEvidence", "ResearchPlan",
    "resolve_output_schema",
]
