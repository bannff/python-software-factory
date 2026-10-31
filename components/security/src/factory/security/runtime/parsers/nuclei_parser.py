"""Parse Nuclei JSONL output into standardized finding dicts."""
from __future__ import annotations

import json
from typing import Any

_SEVERITY_MAP = {"critical": "critical", "high": "high", "medium": "medium",
                 "low": "low", "info": "info", "unknown": "info"}


def parse(raw_output: str) -> list[dict[str, Any]]:
    """Parse nuclei -jsonl output into finding dicts.

    Each line is a JSON object. Returns empty list on malformed input.
    """
    if not raw_output or not raw_output.strip():
        return []

    findings: list[dict[str, Any]] = []
    for line in raw_output.strip().splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not isinstance(obj, dict):
            continue

        template_id = obj.get("template-id", obj.get("templateID", "unknown"))
        severity = _SEVERITY_MAP.get(
            obj.get("info", {}).get("severity", "info"), "info")
        matched = obj.get("matched-at", obj.get("matched", ""))
        name = obj.get("info", {}).get("name", template_id)
        desc = obj.get("info", {}).get("description", "")
        cwe_tags = [t for t in obj.get("info", {}).get("classification", {}).get(
            "cwe-id", []) if t]
        cwe = cwe_tags[0] if cwe_tags else ""
        extracted = obj.get("extracted-results", [])

        findings.append({
            "title": f"[{template_id}] {name}",
            "severity": severity,
            "cwe": cwe,
            "description": desc or f"Nuclei template {template_id} matched",
            "location": matched,
            "evidence": json.dumps(extracted) if extracted else "",
        })

    return findings
