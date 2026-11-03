"""Neutral Finding shape projected from a graph Finding row.

The graph stores security-flavoured columns (cwe, affected_resource_arn, file,
line_*); this maps them onto a domain-agnostic object so the UI can render any
kind of finding. Legacy columns stay on the row for compatibility.
"""
from __future__ import annotations

from typing import Any

_SECURITY_COLUMNS = ("cwe", "vuln_class", "finding_type", "affected_resource_arn")


def _text(row: dict[str, Any], key: str) -> str:
    value = row.get(key)
    return "" if value is None else str(value)


def _kind(row: dict[str, Any]) -> str:
    if _text(row, "kind"):
        return _text(row, "kind")
    return "security" if any(row.get(c) for c in _SECURITY_COLUMNS) else "other"


def _subject(row: dict[str, Any]) -> dict[str, str]:
    if _text(row, "subject_type") or _text(row, "subject_id"):
        return {"type": _text(row, "subject_type"), "id": _text(row, "subject_id"),
                "location": _text(row, "location")}
    if row.get("affected_resource_arn"):
        return {"type": "resource", "id": _text(row, "affected_resource_arn"),
                "location": _text(row, "location")}
    if row.get("file"):
        span = f":{row['line_start']}" if row.get("line_start") is not None else ""
        return {"type": "file", "id": _text(row, "file"),
                "location": _text(row, "location") or f"{row['file']}{span}"}
    return {"type": "", "id": "", "location": _text(row, "location")}


def _refs(row: dict[str, Any]) -> list[dict[str, str]]:
    refs = [{"type": "graph_node", "id": _text(row, "id")}]
    if row.get("run_id"):
        refs.append({"type": "run", "id": _text(row, "run_id")})
    return refs


def neutral(row: dict[str, Any]) -> dict[str, Any]:
    taxonomy = [{"scheme": "cwe", "id": _text(row, "cwe"), "label": ""}] if row.get("cwe") else []
    if row.get("vuln_class"):
        taxonomy.append({"scheme": "vuln_class", "id": _text(row, "vuln_class"), "label": ""})
    return {
        "id": _text(row, "id"), "title": _text(row, "title"), "severity": _text(row, "severity"),
        "state": _text(row, "state"), "created_at": _text(row, "created_at"),
        "kind": _kind(row), "category": _text(row, "category") or _text(row, "finding_type"),
        "description": _text(row, "description"), "evidence": _text(row, "evidence"),
        "remediation": _text(row, "remediation"), "subject": _subject(row),
        "source": {"brick": "", "tool": "", "agent_id": _text(row, "agent_id"),
                   "run_id": _text(row, "run_id"), "invocation_id": "", "session_id": ""},
        "taxonomy": taxonomy, "refs": _refs(row),
        "graded": {"verdict": _text(row, "verdict"), "human_verdict": _text(row, "human_verdict"),
                   "graded_by": _text(row, "graded_by"), "graded_at": _text(row, "graded_at")},
    }
