"""In-memory finding persistence adapter (default fallback).

Stores analyses and findings in a plain dict. Ephemeral — data is
lost on restart. Used when no external persistence is configured.
"""

from __future__ import annotations

from typing import Any


class MemoryFindingPersistence:
    """In-memory persistence for security findings."""

    def __init__(self) -> None:
        self._analyses: dict[str, dict[str, Any]] = {}

    def persist_analysis(
        self, analysis_id: str, analysis_type: str, target: str,
        findings: list[dict[str, Any]], summary: str | None = None,
    ) -> dict[str, Any]:
        record = {
            "analysis_id": analysis_id,
            "analysis_type": analysis_type,
            "target": target,
            "findings": findings,
            "summary": summary,
            "finding_count": len(findings),
        }
        self._analyses[analysis_id] = record
        return {"persisted": True, "backend": "memory", **record}

    def get_analysis(self, analysis_id: str) -> dict[str, Any] | None:
        return self._analyses.get(analysis_id)

    def list_analyses(self, limit: int = 50) -> list[dict[str, Any]]:
        return list(self._analyses.values())[:limit]

    def get_findings(
        self, severity: str | None = None, limit: int = 50,
    ) -> list[dict[str, Any]]:
        all_findings: list[dict[str, Any]] = []
        for analysis in self._analyses.values():
            for f in analysis.get("findings", []):
                if severity and f.get("severity") != severity:
                    continue
                all_findings.append({**f, "analysis_id": analysis["analysis_id"]})
        return all_findings[:limit]

    def health_check(self) -> dict[str, Any]:
        return {"healthy": True, "backend": "memory", "count": len(self._analyses)}
