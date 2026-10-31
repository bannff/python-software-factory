"""Column catalogs for the NetworkX run-scoped typed reads.

Data-only: the flat scalar columns projected by ``networkx_runs`` for
Finding and ToolInvocation rows. Kept in a sibling module so
``networkx_runs.py`` stays under the 200-LOC cap (bd tz8hi). The neo4j
adapter keeps its own Cypher projection in ``_neo4j_finding``; these two
must stay symmetric.
"""

from __future__ import annotations

_FINDING_SCALAR_PROPS = (
    "id", "title", "description", "severity", "location",
    "remediation", "cwe", "evidence", "verdict", "run_id", "app",
    "affected_resource_arn", "finding_type", "category", "created_at",
    "file", "function", "line_start", "line_end", "agent_id", "vuln_class",
    # Verification oracle state (neutral; bd python-factory-216ti Contract B).
    "state",
    # Human-as-labeler grade (domain-neutral; written by either cockpit).
    "human_verdict", "graded_by", "graded_at", "graded_source",
)
_INVOCATION_SCALAR_PROPS = (
    "tool_name", "success", "latency_ms", "created_at",
    "error", "workflow_run_id", "args_summary", "caller", "result_summary",
    "session_id", "principal_id", "sequence",
)
