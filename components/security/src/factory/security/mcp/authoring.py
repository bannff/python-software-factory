"""Unconditionally registered, typed authoring Security MCP tools."""
from __future__ import annotations
from typing import Any
from factory.mcp_utils.interface import ToolResult, authoring as authoring_decorator
from .contracts.base import EmptyInput
from .contracts.authoring import (
    AuthoringStatusOutput,
    RuleInput,
    RuleOutput,
    RulesOutput,
    TaxonomySeedOutput,
    UpsertRuleInput,
)

def _result(value: dict) -> RuleOutput:
    return RuleOutput(success=bool(value.get("success", "error" not in value)),error=value.get("error"),details=value)

def register(mcp: Any, runtime, manager) -> None:
    from ..authoring import AuthoringError
    @mcp.tool(name="security.authoring.get_status")
    @authoring_decorator(input_model=EmptyInput, output_model=AuthoringStatusOutput)
    def authoring_get_status() -> ToolResult[AuthoringStatusOutput]:
        if not manager: return AuthoringStatusOutput(enabled=False,message="Authoring tools disabled")
        value=manager.get_status(); return AuthoringStatusOutput(enabled=bool(value.get("enabled",False)),message=value.get("message"),details=value)
    @mcp.tool(name="security.authoring.list_rules")
    @authoring_decorator(input_model=EmptyInput, output_model=RulesOutput)
    def authoring_list_rules() -> ToolResult[RulesOutput]:
        if not manager: raise AuthoringError("Authoring tools disabled")
        value=manager.list_rules(); rules=value.get("rules",value if isinstance(value,list) else []); return RulesOutput(rules=rules,count=len(rules))
    @mcp.tool(name="security.authoring.upsert_rule")
    @authoring_decorator(input_model=UpsertRuleInput, output_model=RuleOutput)
    def authoring_upsert_rule(id:str,config:dict,dry_run:bool=False) -> ToolResult[RuleOutput]:
        if not manager: raise AuthoringError("Authoring tools disabled")
        return _result(manager.upsert_rule(id=id,config=config,dry_run=dry_run))
    @mcp.tool(name="security.authoring.delete_rule")
    @authoring_decorator(input_model=RuleInput, output_model=RuleOutput)
    def authoring_delete_rule(id:str) -> ToolResult[RuleOutput]:
        if not manager: raise AuthoringError("Authoring tools disabled")
        return _result(manager.delete_rule(id=id))
    @mcp.tool(name="security_seed_cwe_taxonomy")
    @authoring_decorator(input_model=EmptyInput, output_model=TaxonomySeedOutput)
    def security_seed_cwe_taxonomy() -> ToolResult[TaxonomySeedOutput]:
        from ..runtime.cwe_taxonomy import seed_cwe_taxonomy
        value=seed_cwe_taxonomy(); return TaxonomySeedOutput(success=bool(value.get("success", "error" not in value)),error=value.get("error"),details=value)
    @mcp.tool(name="security_seed_ocsf_taxonomy")
    @authoring_decorator(input_model=EmptyInput, output_model=TaxonomySeedOutput)
    def security_seed_ocsf_taxonomy() -> ToolResult[TaxonomySeedOutput]:
        from ..runtime.ocsf_taxonomy import seed_ocsf_taxonomy
        value=seed_ocsf_taxonomy(); return TaxonomySeedOutput(success=bool(value.get("success", "error" not in value)),error=value.get("error"),details=value)
