"""MCP Prompt registration for security brick.

Prompts provide guided workflows for common tasks:
- Running security analyses
- Generating threat models
- Reviewing and triaging findings
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from typing import Any

if TYPE_CHECKING:
    from ..runtime.runtime import SecurityRuntime


def register(mcp: Any, runtime: "SecurityRuntime") -> None:
    """Register all security prompts with the MCP server."""

    @mcp.prompt()
    def analyze_target(target: str, analysis_type: str = "code_analysis") -> str:
        """Generate guidance for analyzing a target."""
        return f"""Analyze security of: {target}

Steps:
1. Run analysis: security.analyze("{target}", "{analysis_type}")
2. Review findings in the result
3. For each finding, check severity and remediation
4. Generate report or take action on critical/high findings

Available analysis types: threat_model, code_analysis, pen_test, recon, vulnerability_scan"""

    @mcp.prompt()
    def threat_model(target: str, context: str = "") -> str:
        """Generate guidance for threat modeling (requires llm_gateway brick)."""
        return f"""Generate threat model for: {target}

Context: {context or "Not specified"}

Note: Threat modeling requires the llm_gateway brick to be available.
The security brick composes llm_gateway for LLM-powered analysis.

Steps:
1. Run: security.threat_model("{target}", "{context}")
2. Review identified threats using STRIDE methodology:
   - Spoofing: Can identity be faked?
   - Tampering: Can data be modified?
   - Repudiation: Can actions be denied?
   - Information Disclosure: Can data leak?
   - Denial of Service: Can service be disrupted?
   - Elevation of Privilege: Can access be escalated?
3. Evaluate proposed mitigations
4. Document assumptions and data flows
5. Prioritize threats by risk"""

    @mcp.prompt()
    def ingest_ground_truth(gt_id: str = "", service_name: str = "") -> str:
        """Generate guidance for ingesting a Ground Truth entry into the IDOR pipeline."""
        return f"""Ingest a Ground Truth (GT) entry for IDOR detection.

GT ID: {gt_id or "<your-gt-id>"}
Service: {service_name or "<service-name>"}

Steps:
1. Get the GT schema: read_brick_resource("security", "security://schemas/gt-entry")
2. Prepare your GT JSON matching the schema (gt_id, cwe, service_name, ground_truth,
   code_evidence, runtime_evidence, exploit_evidence, fix_evidence)
3. Ingest: security_ingest_gt_entry(gt_json={{...}})
   This creates:
   - KB document (semantic search via kb_search)
   - GTEntry graph node (gt-{{gt_id}})
   - AppEndpoint node linked to GTEntry
   - CodeLocation nodes linked to GTEntry
   - Commit node linked to GTEntry
   - CLASSIFIED_AS edge to CWECategory
4. Verify with `graph_find_entities(entity_type="GTEntry", properties={"gt_id": "{gt_id}"})`
5. Run the IDOR scan swarm: spawn_swarm(swarm_id="rt-scan-idor-swarm-v2",
   task="Detect IDOR in {{service_name}}")
   Use get_swarm_registry to list the current swarm options.

Sample GT entry for the idor-warehouse challenge app:
  See projects/companion_x/challenges/idor_warehouse/gt_entries.json for 3 ready-to-use entries."""

    @mcp.prompt()
    def review_findings(analysis_id: str) -> str:
        """Generate guidance for reviewing security findings."""
        analysis = runtime.get_analysis(analysis_id)
        if analysis:
            severity_summary: dict[str, int] = {}
            for f in analysis.findings:
                sev = f.severity.value
                severity_summary[sev] = severity_summary.get(sev, 0) + 1
            status_info = (
                f"- Total Findings: {len(analysis.findings)}\n"
                f"- By Severity: {severity_summary}\n"
                f"- Target: {analysis.target}\n"
                f"- Status: {analysis.status}"
            )
        else:
            status_info = "(Analysis not found)"

        return f"""Review findings from analysis {analysis_id}:

Analysis Summary:
{status_info}

Review Steps:
1. Get analysis: security.get_analysis("{analysis_id}")
2. Sort findings by severity (critical > high > medium > low)
3. For each finding:
   - Verify the issue exists
   - Assess actual risk in context
   - Plan remediation
4. Track remediation progress
5. Re-run analysis after fixes to verify"""
