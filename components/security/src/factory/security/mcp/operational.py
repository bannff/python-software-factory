"""Operational typed MCP tools for Security."""
from __future__ import annotations
from typing import Any
from factory.mcp_utils.interface import ToolResult, operational
from ..core import AnalysisType
from ..runtime.models import SecurityConfig
from .contracts.operational import (
    AnalyzeInput,
    AnalyzeOutput,
    ClassifyFindingInput,
    CodeReviewInput,
    ConformFindingInput,
    FindingsForRunInput,
    FindingsForRunOutput,
    GroundTruthInput,
    GroundTruthOutput,
    PersistedAnalysesInput,
    PersistedAnalysesOutput,
    PersistedFindingsInput,
    PersistedFindingsOutput,
    ReconInput,
    TaxonomyOutput,
    ThreatModelInput,
    ThreatModelOutput,
)

def _taxonomy(result: dict) -> TaxonomyOutput:
    return TaxonomyOutput(success=bool(result.get("success", "error" not in result)), error=result.get("error"), details=result)

def register(mcp: Any, runtime) -> None:
    @mcp.tool(name="security.analyze")
    @operational(input_model=AnalyzeInput, output_model=AnalyzeOutput)
    async def analyze(target:str,analysis_type:str="code_analysis",max_findings:int=100,include_info:bool=False) -> ToolResult[AnalyzeOutput]:
        try: atype=AnalysisType(analysis_type)
        except ValueError: return AnalyzeOutput(success=False,error=f"Invalid analysis type: {analysis_type}")
        result=await runtime.analyze(target,atype,SecurityConfig(max_findings=max_findings,include_info=include_info)); return AnalyzeOutput(success=True,analysis=result.model_dump())
    @mcp.tool(name="security.threat_model")
    @operational(input_model=ThreatModelInput, output_model=ThreatModelOutput)
    async def threat_model(target:str,context:str="") -> ToolResult[ThreatModelOutput]:
        return ThreatModelOutput.model_validate(await runtime.threat_model(target, context))
    @mcp.tool(name="security.code_review")
    @operational(input_model=CodeReviewInput, output_model=AnalyzeOutput)
    async def code_review(code:str,language:str="python",focus:str="") -> ToolResult[AnalyzeOutput]:
        result=await runtime.analyze(f"code:{language}",AnalysisType.CODE_ANALYSIS,SecurityConfig()); return AnalyzeOutput(success=True,analysis=result.model_dump())
    @mcp.tool(name="security.recon")
    @operational(input_model=ReconInput, output_model=AnalyzeOutput)
    async def recon(target:str,depth:str="shallow") -> ToolResult[AnalyzeOutput]:
        result=await runtime.analyze(target,AnalysisType.RECON,SecurityConfig()); return AnalyzeOutput(success=True,analysis=result.model_dump())
    @mcp.tool(name="security.list_persisted_findings")
    @operational(input_model=PersistedFindingsInput, output_model=PersistedFindingsOutput)
    def list_persisted_findings(severity:str|None=None,limit:int=50) -> ToolResult[PersistedFindingsOutput]:
        findings=runtime.get_persisted_findings(severity=severity,limit=limit); return PersistedFindingsOutput(findings=findings,count=len(findings))
    @mcp.tool(name="security.list_persisted_analyses")
    @operational(input_model=PersistedAnalysesInput, output_model=PersistedAnalysesOutput)
    def list_persisted_analyses(limit:int=50) -> ToolResult[PersistedAnalysesOutput]:
        analyses=runtime.list_persisted_analyses(limit=limit); return PersistedAnalysesOutput(analyses=analyses,count=len(analyses))
    @mcp.tool(name="security_classify_finding")
    @operational(input_model=ClassifyFindingInput, output_model=TaxonomyOutput)
    def security_classify_finding(finding_id:str,cwe_id:str) -> ToolResult[TaxonomyOutput]:
        from ..runtime.cwe_taxonomy import classify_finding
        return _taxonomy(classify_finding(finding_id,cwe_id))
    @mcp.tool(name="security_conform_finding")
    @operational(input_model=ConformFindingInput, output_model=TaxonomyOutput)
    def security_conform_finding(entity_id:str,class_uid:int) -> ToolResult[TaxonomyOutput]:
        from ..runtime.ocsf_taxonomy import conform_finding
        return _taxonomy(conform_finding(entity_id,class_uid))
    @mcp.tool(name="security_ingest_gt_entry")
    @operational(input_model=GroundTruthInput, output_model=GroundTruthOutput)
    def security_ingest_gt_entry(gt_json:dict) -> ToolResult[GroundTruthOutput]:
        from ..runtime.gt_ingestion import ingest_gt_entry
        result=ingest_gt_entry(gt_json); return GroundTruthOutput(success=bool(result.get("success", "error" not in result)),error=result.get("error"),details=result)
    @mcp.tool(name="security_list_findings_for_run")
    @operational(input_model=FindingsForRunInput, output_model=FindingsForRunOutput)
    def security_list_findings_for_run(run_id:str,app:str="",limit:int=50) -> ToolResult[FindingsForRunOutput]:
        from factory.mcp_server.interface import get_aggregator,get_server
        get_server(); agg=get_aggregator()
        if agg is None: return FindingsForRunOutput(run_id=run_id,app=app,limit=limit,rows=[],count=0,error="mcp_aggregator_unavailable")
        result=agg.invoke_tool("graph_graph_get_findings_for_run",run_id=run_id,app=app,limit=limit)
        if not result or not result.ok or result.data is None: return FindingsForRunOutput(run_id=run_id,app=app,limit=limit,rows=[],count=0,error=getattr(result,"error",None) or "graph_get_findings_for_run_failed")
        rows=list(result.data.rows); return FindingsForRunOutput(run_id=run_id,app=app,limit=limit,rows=rows,count=len(rows))
