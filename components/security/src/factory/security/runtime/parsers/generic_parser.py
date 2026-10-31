"""Generic text parser for curl, gobuster, sqlmap output."""
from __future__ import annotations

import re
from typing import Any


def parse_http_probe(raw_output: str) -> list[dict[str, Any]]:
    """Parse curl -w '%{http_code} %{size_download} %{time_total}' output."""
    if not raw_output or not raw_output.strip():
        return []
    findings: list[dict[str, Any]] = []
    for line in raw_output.strip().splitlines():
        parts = line.strip().split()
        if not parts:
            continue
        code = parts[0]
        size = parts[1] if len(parts) > 1 else "0"
        time_s = parts[2] if len(parts) > 2 else "0"
        findings.append({
            "title": f"HTTP {code} response",
            "severity": "info",
            "cwe": "CWE-200",
            "description": f"Status {code}, size {size}B, time {time_s}s",
            "location": "",
            "evidence": line.strip(),
        })
    return findings


def parse_web_fuzz(raw_output: str) -> list[dict[str, Any]]:
    """Parse gobuster dir output (lines with Status: codes)."""
    if not raw_output or not raw_output.strip():
        return []
    findings: list[dict[str, Any]] = []
    for line in raw_output.strip().splitlines():
        m = re.search(r"(/\S+)\s+.*\(Status:\s*(\d+)", line)
        if not m:
            continue
        path, status = m.group(1), m.group(2)
        findings.append({
            "title": f"Discovered path: {path} ({status})",
            "severity": "low" if status == "200" else "info",
            "cwe": "CWE-538",
            "description": f"Directory/file found at {path}",
            "location": path,
            "evidence": line.strip(),
        })
    return findings


def parse_sql_inject(raw_output: str) -> list[dict[str, Any]]:
    """Parse sqlmap --batch output for injection confirmations."""
    if not raw_output or not raw_output.strip():
        return []
    findings: list[dict[str, Any]] = []
    for line in raw_output.strip().splitlines():
        if "is vulnerable" in line.lower() or "injectable" in line.lower():
            findings.append({
                "title": "SQL Injection confirmed",
                "severity": "critical",
                "cwe": "CWE-89",
                "description": line.strip(),
                "location": "",
                "evidence": line.strip(),
            })
    return findings
