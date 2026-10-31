"""Pydantic models for security component."""

from typing import Any

from pydantic import BaseModel, Field

from ..core import AnalysisType, Severity


class SecurityConfig(BaseModel):
    """Security analysis configuration."""

    max_findings: int = Field(default=100, ge=1, le=1000)
    include_info: bool = False
    timeout_seconds: int = Field(default=300, ge=30, le=3600)


class Finding(BaseModel):
    """Security finding."""

    id: str
    title: str
    severity: Severity
    description: str
    location: str | None = None
    remediation: str | None = None
    references: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class AnalysisResult(BaseModel):
    """Result of security analysis."""

    analysis_id: str
    analysis_type: AnalysisType
    target: str
    status: str
    findings: list[Finding] = Field(default_factory=list)
    summary: str | None = None
    duration_ms: int | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class ThreatModel(BaseModel):
    """Threat model output."""

    target: str
    threats: list[dict[str, Any]] = Field(default_factory=list)
    mitigations: list[dict[str, Any]] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)
    data_flows: list[dict[str, Any]] = Field(default_factory=list)
