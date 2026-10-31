"""Strict DTOs for deterministic Security MCP tools."""
from __future__ import annotations
from typing import Any
from .base import DTO

class CapabilitiesOutput(DTO):
    name: str; version: str; tools: dict[str, list[str]]; adapters: list[str]; features: list[str]
class HealthOutput(DTO):
    healthy: bool; details: dict[str, Any] = {}
class ConfigSchemaOutput(DTO):
    type: str; properties: dict[str, dict[str, Any]]
class AnalysesOutput(DTO):
    count: int; analyses: list[dict[str, Any]]
class AnalysisInput(DTO):
    analysis_id: str
class AnalysisOutput(DTO):
    found: bool; analysis: dict[str, Any] | None = None
class TypesOutput(DTO):
    types: list[str]
class EndpointScanInput(DTO):
    source_code: str; framework: str = "auto"; file_path: str = ""
class EndpointScanOutput(DTO):
    endpoints: list[dict[str, Any]]; count: int
class ConfidenceInput(DTO):
    agent_consensus: int = 1; total_agents: int = 3; has_taint_trace: bool = False; has_mitigating_control: bool = False; has_code_evidence: bool = False; is_sensitive_operation: bool = False; historical_tp_rate: float = -1.0; confidence_score: float = 0.5
class ConfidenceOutput(DTO):
    confidence_level: str; confidence_score: float; reason: str; level_index: int
class TaintInput(DTO):
    source_code: str; param: str; taint_sinks: str = "[]"; taint_sources: str = "[]"; endpoint: str = ""; file_path: str = ""
class TaintOutput(DTO):
    endpoint: str; param: str; file: str; hops: list[dict[str, Any]]; hop_count: int; sink_reached: bool; auth_gap: bool; auth_checks: list[dict[str, Any]]
