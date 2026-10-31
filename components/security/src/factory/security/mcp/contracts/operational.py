"""Strict DTOs for operational Security MCP tools."""
from __future__ import annotations
from typing import Any
from .base import DTO

class AnalyzeInput(DTO):
    target: str; analysis_type: str = "code_analysis"; max_findings: int = 100; include_info: bool = False
class AnalyzeOutput(DTO):
    success: bool; analysis: dict[str, Any] | None = None; error: str | None = None
class ThreatModelInput(DTO):
    target: str; context: str = ""
class ThreatModelOutput(DTO):
    target: str | None = None
    analysis: str | None = None
    error: str | None = None
class CodeReviewInput(DTO):
    code: str; language: str = "python"; focus: str = ""
class ReconInput(DTO):
    target: str; depth: str = "shallow"
class PersistedFindingsInput(DTO):
    severity: str | None = None; limit: int = 50
class PersistedFindingsOutput(DTO):
    findings: list[dict[str, Any]]; count: int
class PersistedAnalysesInput(DTO):
    limit: int = 50
class PersistedAnalysesOutput(DTO):
    analyses: list[dict[str, Any]]; count: int
class ClassifyFindingInput(DTO):
    finding_id: str; cwe_id: str
class ConformFindingInput(DTO):
    entity_id: str; class_uid: int
class TaxonomyOutput(DTO):
    success: bool; error: str | None = None; details: dict[str, Any] = {}
class GroundTruthInput(DTO):
    gt_json: dict[str, Any]
class GroundTruthOutput(DTO):
    success: bool; error: str | None = None; details: dict[str, Any] = {}
class FindingsForRunInput(DTO):
    run_id: str; app: str = ""; limit: int = 50
class FindingsForRunOutput(DTO):
    run_id: str; app: str; limit: int = 50; rows: list[dict[str, Any]]; count: int; error: str | None = None
