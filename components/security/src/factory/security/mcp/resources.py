"""MCP Resource registration for security brick.

Resources expose static/queryable data:
- Schemas for security configuration and findings
- Documentation on analysis types and adapters
- Live analysis and findings data
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

from typing import Any

if TYPE_CHECKING:
    from ..runtime.runtime import SecurityRuntime

DOCS = {
    "overview": """# Security Component

Polymorphic security operations with pluggable analysis adapters.

## Analysis Types

- **threat_model**: STRIDE-based threat modeling
- **code_analysis**: Static code security analysis
- **pen_test**: Penetration testing operations
- **recon**: Reconnaissance and information gathering
- **vulnerability_scan**: Vulnerability scanning

## Usage

```python
from factory.security.interface import Runtime, create_server
from factory.security.runtime.adapters.mock import MockAnalyzerAdapter

adapter = MockAnalyzerAdapter()
runtime = Runtime(adapter)

result = await runtime.analyze("target", AnalysisType.CODE_ANALYSIS)
```
""",
    "adapters": """# Security Adapters

## Threat Modeling Adapter
Uses LLM for STRIDE-based threat analysis.

## Code Analysis Adapter
Static analysis for security vulnerabilities.

## Pen Testing Adapter
Automated penetration testing tools.

## Recon Adapter
Information gathering and reconnaissance.
""",
    "severity": """# Severity Levels

- **critical**: Immediate action required, system compromise likely
- **high**: Significant risk, should be addressed urgently
- **medium**: Moderate risk, plan remediation
- **low**: Minor risk, address when convenient
- **info**: Informational, no immediate action needed
""",
}


_GT_ENTRY_SCHEMA: dict = {
    "title": "ART Ground Truth Entry",
    "type": "object",
    "required": ["gt_id", "vulnerability_class", "cwe"],
    "properties": {
        "gt_id": {"type": "string"},
        "vulnerability_class": {"type": "string"},
        "cwe": {"type": "string"},
        "service_name": {"type": "string"},
        "ground_truth": {"type": "object"},
        "code_evidence": {"type": "object"},
        "runtime_evidence": {"type": "object"},
        "exploit_evidence": {"type": "object"},
        "fix_evidence": {"type": "object"},
    },
    "description": (
        "See security://schemas/gt-entry for full schema. "
        "Use security_ingest_gt_entry to ingest. "
        "Full example: projects/companion_x/challenges/idor_warehouse/gt_entries.json"
    ),
}


def register(mcp: Any, runtime: "SecurityRuntime") -> None:
    """Register all security resources with the MCP server."""
    from ..runtime.models import SecurityConfig, Finding, AnalysisResult

    @mcp.resource("security://schemas/config")
    def resource_config_schema() -> str:
        """Get the JSON schema for security configuration."""
        return json.dumps(SecurityConfig.model_json_schema(), indent=2)

    @mcp.resource("security://schemas/finding")
    def resource_finding_schema() -> str:
        """Get the JSON schema for security findings."""
        return json.dumps(Finding.model_json_schema(), indent=2)

    @mcp.resource("security://schemas/analysis")
    def resource_analysis_schema() -> str:
        """Get the JSON schema for analysis results."""
        return json.dumps(AnalysisResult.model_json_schema(), indent=2)

    @mcp.resource("security://docs")
    def resource_docs_list() -> str:
        """List available security documentation."""
        docs = [{"name": k, "title": k.replace("_", " ").title()} for k in DOCS.keys()]
        return json.dumps({"docs": docs}, indent=2)

    @mcp.resource("security://docs/{doc_name}")
    def resource_docs(doc_name: str) -> str:
        """Get security documentation by name."""
        if doc_name in DOCS:
            return DOCS[doc_name]
        available = list(DOCS.keys())
        return f"Unknown doc: {doc_name}. Available: {available}"

    @mcp.resource("security://findings")
    def resource_findings() -> str:
        """List all findings from analyses."""
        analyses = runtime.list_analyses()
        all_findings = []
        for a in analyses:
            all_findings.extend([f.model_dump() for f in a.findings])
        return json.dumps(
            {"findings": all_findings, "count": len(all_findings)}, indent=2
        )

    @mcp.resource("security://backends")
    def resource_backends() -> str:
        """List available security backends."""
        return json.dumps({
            "backends": [
                {"name": "threat_modeling", "description": "LLM-based threat modeling"},
                {"name": "code_analysis", "description": "Static code analysis"},
                {"name": "pen_testing", "description": "Penetration testing"},
                {"name": "recon", "description": "Reconnaissance"},
                {"name": "mock", "description": "Mock adapter for testing"},
            ],
        }, indent=2)

    @mcp.resource("security://health")
    def resource_health() -> str:
        """Get security health status."""
        analyses = runtime.list_analyses()
        total_findings = sum(len(a.findings) for a in analyses)
        return json.dumps({
            "healthy": True,
            "adapter": runtime.analyzer.__class__.__name__,
            "analyses": {
                "total": len(analyses),
                "findings": total_findings,
            },
            "message": "Security runtime operational",
        }, indent=2)

    @mcp.resource("security://schemas/gt-entry")
    def resource_gt_entry_schema() -> str:
        """Get the ART Ground Truth entry schema for IDOR pipeline ingestion."""
        return json.dumps(_GT_ENTRY_SCHEMA, indent=2)

    @mcp.resource("security://factory")
    def resource_factory_ref() -> str:
        """Reference to factory-level resources."""
        return json.dumps({
            "message": "For workspace-level operations, use foreman tools",
            "foreman_tools": [
                "foreman_info", "foreman_check",
                "foreman_guardian_check", "foreman_get_repo_guardrails",
            ],
            "foreman_resources": [
                "foreman://docs", "foreman://bricks", "foreman://schema/brick-yaml",
            ],
        }, indent=2)
