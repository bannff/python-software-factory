"""Per-finding builders for the experiment-report shaper.

Extracted from ``workflow_report_findings`` to keep that file under the
200 LOC ceiling after ``count_labels`` + ``taxonomy_edges`` thread
through the engine (bd:python-factory-tmlrx + python-factory-st587).
The builder helpers keep their original module-private names so callers
inside ``workflow_report_findings`` can keep importing them locally.
"""
from __future__ import annotations

import json
import os
from typing import Any


def _build_finding(
    node: dict, suspected: list[dict], exploits: list[dict],
) -> dict:
    """Build a rich finding dict from a Finding node + correlated data."""
    file = node.get("file", "")
    function = node.get("function", "")
    file_base = os.path.basename(file)
    matching = [
        s for s in suspected
        if os.path.basename(s.get("file", "")) == file_base
        and s.get("function", "") == function
    ]
    best = max(matching, key=lambda s: s.get("confidence", 0), default={})
    exploit = _find_exploit(exploits, file_base, function)
    result = {
        "id": node.get("id", ""),
        "endpoint": f"{node.get('method', 'GET')} {node.get('path', file)}",
        "file": f"{file}:{node.get('line_start', '')}—{node.get('line_end', '')}",
        "function": function,
        "parameter": best.get("parameter", node.get("parameter", "")),
        "cwe": node.get("cwe", node.get("cwe_id", "")),
        "cwe_secondary": node.get("cwe_secondary", ""),
        "severity": node.get("severity", best.get("severity", "MEDIUM")),
        "confidence_level": node.get("confidence_level",
                                     best.get("confidence_level", "")),
        "confidence_score": node.get("confidence", best.get("confidence", 0)),
        "verdict": node.get("verdict", ""),
        "consensus": node.get("contributing_agents", ""),
        "sink": best.get("sink", node.get("sink", "")),
        "reasoning": best.get("reasoning", node.get("reasoning", "")),
        "attack_chain": best.get("attack_chain", ""),
        "taint_trace": _extract_taint(best),
        "dynamic_verification_status": node.get(
            "dynamic_verification_status", "not_tested"),
    }
    if exploit:
        result["dast_evidence"] = _dast_evidence(exploit)
        result["dynamic_verification_status"] = "verified_finding"
    return result


def _build_exploit_finding(node: dict) -> dict:
    """Build a finding dict from a ProvenExploit node (DAST-only fallback)."""
    method = node.get("method", "")
    path = node.get("path", "")
    return {
        "id": node.get("id", ""),
        "endpoint": f"{method} {path}" if method else path,
        "file": "", "function": "",
        "parameter": node.get("parameter", ""),
        "cwe": node.get("cwe", ""), "cwe_secondary": "",
        "severity": node.get("severity", "HIGH"),
        "confidence_level": "Confirmed", "confidence_score": 1.0,
        "verdict": "CONFIRMED", "consensus": "", "sink": "",
        "reasoning": node.get("reasoning", ""),
        "attack_chain": node.get("attack_chain", ""),
        "taint_trace": {"hop_count": 0, "sink_reached": False,
                        "auth_gap": False, "auth_checks": [], "hops": []},
        "dynamic_verification_status": "verified_finding",
        "dast_evidence": _dast_evidence(node),
    }


def _find_exploit(
    exploits: list[dict], file_base: str, function: str,
) -> dict | None:
    """Find a matching ProvenExploit for a finding."""
    for en in exploits:
        ef = os.path.basename(en.get("file", ""))
        if ef == file_base or (en.get("method") and en.get("path")):
            return en
    return None


def _dast_evidence(node: dict) -> dict:
    """DAST evidence sub-dict drawn from a ProvenExploit node."""
    return {
        "http_request": node.get("command_run", node.get("http_request", "")),
        "http_status": node.get("actual_status", node.get("http_status", 0)),
        "expected_secure": node.get("expected_secure", 403),
        "response_body": node.get("actual_output",
                                  node.get("response_body", "")),
        "server_feedback": node.get("server_feedback", ""),
    }


def _extract_taint(node: dict) -> dict:
    """Extract taint trace from a SuspectedVuln node's properties."""
    taint = node.get("taint_trace", {})
    if isinstance(taint, str):
        try:
            taint = json.loads(taint)
        except Exception:
            taint = {}
    if not isinstance(taint, dict):
        taint = {}
    return {
        "hop_count": taint.get("hop_count", 0),
        "sink_reached": taint.get("sink_reached", False),
        "auth_gap": taint.get("auth_gap", False),
        "auth_checks": taint.get("auth_checks", []),
        "hops": taint.get("hops", []),
    }
