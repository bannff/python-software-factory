"""Mock security adapters for testing."""

import uuid
from typing import Any


class MockAnalyzerAdapter:
    """Mock security analyzer for testing."""

    def __init__(self) -> None:
        """Initialize mock adapter."""
        self._analyses: dict[str, dict[str, Any]] = {}

    async def analyze(
        self, target: str, analysis_type: str, options: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        """Run mock analysis."""
        analysis_id = str(uuid.uuid4())
        findings = [
            {
                "id": str(uuid.uuid4()),
                "title": f"Mock {analysis_type} finding",
                "severity": "medium",
                "description": f"Mock finding for {target}",
                "location": target,
                "remediation": "Review and fix",
            }
        ]
        self._analyses[analysis_id] = {"status": "completed", "findings": findings}
        return {
            "analysis_id": analysis_id,
            "findings": findings,
            "summary": f"Mock {analysis_type} analysis of {target}",
            "duration_ms": 100,
        }

    async def get_analysis_status(self, analysis_id: str) -> dict[str, Any]:
        """Get mock analysis status."""
        if analysis_id not in self._analyses:
            return {"status": "not_found"}
        return self._analyses[analysis_id]

    async def cancel_analysis(self, analysis_id: str) -> None:
        """Cancel mock analysis."""
        if analysis_id in self._analyses:
            self._analyses[analysis_id]["status"] = "cancelled"

    def supported_types(self) -> list[str]:
        """Return supported analysis types."""
        return ["threat_model", "code_analysis", "pen_test", "recon", "vulnerability_scan"]

    def health_check(self) -> dict[str, Any]:
        """Check mock adapter health."""
        return {"healthy": True, "adapter": "mock", "analyses": len(self._analyses)}


class MockLLMAdapter:
    """Mock LLM adapter for testing."""

    async def complete_async(
        self, prompt: str, model: str | None = None, **kwargs: Any,
    ) -> Any:
        """Return mock async completion."""
        from types import SimpleNamespace
        return SimpleNamespace(content=f"Mock LLM response for: {prompt[:50]}...")

    def complete(
        self, prompt: str, model: str | None = None, **kwargs: Any,
    ) -> Any:
        """Return mock completion."""
        from types import SimpleNamespace
        return SimpleNamespace(content=f"Mock LLM response for: {prompt[:50]}...")

    def health_check(self) -> dict[str, Any]:
        """Check mock LLM health."""
        return {"available": True, "adapter": "mock"}
