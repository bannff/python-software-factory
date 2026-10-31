"""Bandit-backed security analyzer adapter.

Wraps the `bandit` Python static analysis tool to scan code for
common security issues (B101-B703). Runs bandit as a subprocess
and parses its JSON output into the SecurityAnalyzerPort interface.
"""
from __future__ import annotations

import json
import subprocess
import uuid
from typing import Any

_SEVERITY_MAP = {"LOW": "low", "MEDIUM": "medium", "HIGH": "high"}


class BanditAnalyzerAdapter:
    """Security analyzer using bandit for Python static analysis."""

    def __init__(self, *, bandit_cmd: str = "bandit") -> None:
        self._cmd = bandit_cmd

    async def analyze(
        self, target: str, analysis_type: str, options: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        opts = options or {}
        max_findings = opts.get("max_findings", 100)
        try:
            result = subprocess.run(
                [self._cmd, "-r", target, "-f", "json", "--quiet"],
                capture_output=True, text=True, timeout=300,
            )
            data = json.loads(result.stdout) if result.stdout.strip() else {}
        except (subprocess.TimeoutExpired, FileNotFoundError, json.JSONDecodeError) as e:
            return {"findings": [], "summary": f"Bandit error: {e}", "duration_ms": 0}

        raw_results = data.get("results", [])
        findings = []
        for r in raw_results[:max_findings]:
            findings.append({
                "id": str(uuid.uuid4()),
                "title": f"{r.get('test_id', '?')}: {r.get('test_name', 'unknown')}",
                "severity": _SEVERITY_MAP.get(r.get("issue_severity", ""), "info"),
                "description": r.get("issue_text", ""),
                "location": f"{r.get('filename', '?')}:{r.get('line_number', '?')}",
                "remediation": r.get("more_info"),
            })

        metrics = data.get("metrics", {}).get("_totals", {})
        return {
            "findings": findings,
            "summary": (
                f"Bandit scanned {metrics.get('loc', '?')} LOC, "
                f"found {len(findings)} issue(s)"
            ),
            "duration_ms": 0,
        }

    async def get_analysis_status(self, analysis_id: str) -> dict[str, Any]:
        return {"status": "completed"}

    async def cancel_analysis(self, analysis_id: str) -> None:
        pass  # bandit runs synchronously

    def supported_types(self) -> list[str]:
        return ["code_analysis"]

    def health_check(self) -> dict[str, Any]:
        try:
            r = subprocess.run(
                [self._cmd, "--version"], capture_output=True, text=True, timeout=5,
            )
            return {"healthy": r.returncode == 0, "adapter": "bandit",
                    "version": r.stdout.strip()}
        except Exception as e:
            return {"healthy": False, "adapter": "bandit", "error": str(e)}
