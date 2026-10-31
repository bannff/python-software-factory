"""Deterministic typed MCP tools for Security."""
from __future__ import annotations
import json
from typing import Any
from factory.mcp_utils.interface import ToolResult, deterministic
from ..core import COMPONENT_NAME, COMPONENT_VERSION
from .contracts.base import EmptyInput
from .contracts.deterministic import (
    AnalysesOutput,
    AnalysisInput,
    AnalysisOutput,
    CapabilitiesOutput,
    ConfigSchemaOutput,
    ConfidenceInput,
    ConfidenceOutput,
    EndpointScanInput,
    EndpointScanOutput,
    HealthOutput,
    TaintInput,
    TaintOutput,
    TypesOutput,
)

def register(mcp: Any, runtime) -> None:
    @mcp.tool(name="security.get_capabilities")
    @deterministic(input_model=EmptyInput, output_model=CapabilitiesOutput)
    def get_capabilities() -> ToolResult[CapabilitiesOutput]:
        return CapabilitiesOutput(name=COMPONENT_NAME, version=COMPONENT_VERSION, tools={"deterministic":["security.get_capabilities","security.health_check","security.describe_config_schema","security.list_analyses","security.get_analysis","security.supported_types"],"operational":["security.analyze","security.threat_model","security.code_review","security.recon"]}, adapters=["threat_modeling","code_analysis","pen_testing","recon","mock"], features=["threat_modeling","code_analysis","penetration_testing","reconnaissance","vulnerability_scanning"])
    @mcp.tool(name="security.health_check")
    @deterministic(input_model=EmptyInput, output_model=HealthOutput)
    def health_check() -> ToolResult[HealthOutput]:
        data = runtime.health_check(); return HealthOutput(healthy=bool(data.pop("healthy", False)), details=data)
    @mcp.tool(name="security.describe_config_schema")
    @deterministic(input_model=EmptyInput, output_model=ConfigSchemaOutput)
    def describe_config_schema() -> ToolResult[ConfigSchemaOutput]:
        return ConfigSchemaOutput(type="object", properties={"max_findings":{"type":"integer","default":100},"include_info":{"type":"boolean","default":False},"timeout_seconds":{"type":"integer","default":300}})
    @mcp.tool(name="security.list_analyses")
    @deterministic(input_model=EmptyInput, output_model=AnalysesOutput)
    def list_analyses() -> ToolResult[AnalysesOutput]:
        analyses = runtime.list_analyses(); return AnalysesOutput(count=len(analyses), analyses=[a.model_dump() for a in analyses])
    @mcp.tool(name="security.get_analysis")
    @deterministic(input_model=AnalysisInput, output_model=AnalysisOutput)
    def get_analysis(analysis_id: str) -> ToolResult[AnalysisOutput]:
        analysis = runtime.get_analysis(analysis_id); return AnalysisOutput(found=analysis is not None, analysis=None if analysis is None else analysis.model_dump())
    @mcp.tool(name="security.supported_types")
    @deterministic(input_model=EmptyInput, output_model=TypesOutput)
    def supported_types() -> ToolResult[TypesOutput]:
        return TypesOutput(types=[item.value if hasattr(item,"value") else item for item in runtime.supported_types()])
    @mcp.tool(name="security.scan_endpoints")
    @deterministic(input_model=EndpointScanInput, output_model=EndpointScanOutput)
    def scan_endpoints(source_code: str, framework: str="auto", file_path: str="") -> ToolResult[EndpointScanOutput]:
        from ..runtime.endpoint_scanner import scan_endpoints as scan
        endpoints=scan(source_code, framework, file_path); return EndpointScanOutput(endpoints=endpoints, count=len(endpoints))
    @mcp.tool(name="security.classify_confidence")
    @deterministic(input_model=ConfidenceInput, output_model=ConfidenceOutput)
    def classify_confidence(agent_consensus:int=1,total_agents:int=3,has_taint_trace:bool=False,has_mitigating_control:bool=False,has_code_evidence:bool=False,is_sensitive_operation:bool=False,historical_tp_rate:float=-1.0,confidence_score:float=.5) -> ToolResult[ConfidenceOutput]:
        from ..runtime.confidence import classify
        return classify(agent_consensus=agent_consensus,total_agents=total_agents,has_taint_trace=has_taint_trace,has_mitigating_control=has_mitigating_control,has_code_evidence=has_code_evidence,is_sensitive_operation=is_sensitive_operation,historical_tp_rate=None if historical_tp_rate < 0 else historical_tp_rate,confidence_score=confidence_score)
    @mcp.tool(name="security.trace_taint")
    @deterministic(input_model=TaintInput, output_model=TaintOutput)
    def trace_taint(source_code:str,param:str,taint_sinks:str="[]",taint_sources:str="[]",endpoint:str="",file_path:str="") -> ToolResult[TaintOutput]:
        try: sinks=json.loads(taint_sinks) if isinstance(taint_sinks,str) else taint_sinks; sources=json.loads(taint_sources) if isinstance(taint_sources,str) else taint_sources
        except (ValueError,TypeError): sinks,sources=[],[]
        from ..runtime.taint_tracer import trace
        return trace(source_code=source_code,endpoint=endpoint,param=param,taint_sinks=sinks,taint_sources=sources,file_path=file_path)
