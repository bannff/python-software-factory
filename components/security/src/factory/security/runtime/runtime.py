"""Security runtime - main orchestration layer."""

import uuid
from datetime import datetime, timezone
from typing import Any

from ..core import AnalysisType, Severity
from .models import AnalysisResult, Finding, SecurityConfig
from .ports import FindingPersistencePort, SecurityAnalyzerPort


class SecurityRuntime:
    """Runtime for security analysis operations."""

    def __init__(
        self,
        analyzer: SecurityAnalyzerPort,
        llm: Any | None = None,
        persistence: FindingPersistencePort | None = None,
    ) -> None:
        """Initialize with adapters.

        Args:
            analyzer: Security analysis backend.
            llm: Optional LLMProvider from factory.llm_gateway.interface.
            persistence: Optional finding persistence backend.
                         Defaults to in-memory if not provided.
        """
        self._analyzer = analyzer
        self._llm = llm
        if persistence is None:
            from .adapters.memory_persistence import MemoryFindingPersistence
            persistence = MemoryFindingPersistence()
        self._persistence = persistence
        self._analyses: dict[str, AnalysisResult] = {}

    async def analyze(
        self,
        target: str,
        analysis_type: AnalysisType,
        config: SecurityConfig | None = None,
    ) -> AnalysisResult:
        """Run security analysis."""
        cfg = config or SecurityConfig()
        analysis_id = str(uuid.uuid4())
        
        result = await self._analyzer.analyze(
            target, analysis_type.value, {"max_findings": cfg.max_findings}
        )
        
        findings = [
            Finding(
                id=f.get("id", str(uuid.uuid4())),
                title=f.get("title", "Unknown"),
                severity=Severity(f.get("severity", "info")),
                description=f.get("description", ""),
                location=f.get("location"),
                remediation=f.get("remediation"),
            )
            for f in result.get("findings", [])
        ]
        
        analysis = AnalysisResult(
            analysis_id=analysis_id,
            analysis_type=analysis_type,
            target=target,
            status="completed",
            findings=findings,
            summary=result.get("summary"),
            duration_ms=result.get("duration_ms"),
        )
        self._analyses[analysis_id] = analysis

        # Persist to backend (graph, memory, etc.)
        self._persistence.persist_analysis(
            analysis_id=analysis_id,
            analysis_type=analysis_type.value,
            target=target,
            findings=[f.model_dump() for f in findings],
            summary=result.get("summary"),
        )

        return analysis

    async def threat_model(self, target: str, context: str = "") -> dict[str, Any]:
        """Generate threat model using LLM (via llm_gateway brick)."""
        if not self._llm:
            return {"error": "LLM adapter not configured — compose llm_gateway brick"}
        
        prompt = f"Generate a threat model for: {target}\nContext: {context}"
        try:
            response = await self._llm.complete_async(
                prompt, model=None, max_tokens=2048, temperature=0.3,
            )
            return {"target": target, "analysis": response.content}
        except AttributeError:
            # Fallback for sync-only providers
            response = self._llm.complete(
                prompt, model=None, max_tokens=2048, temperature=0.3,
            )
            return {"target": target, "analysis": response.content}

    def get_analysis(self, analysis_id: str) -> AnalysisResult | None:
        """Get analysis result (in-memory cache, then persistence)."""
        cached = self._analyses.get(analysis_id)
        if cached:
            return cached
        return None

    def list_analyses(self) -> list[AnalysisResult]:
        """List all analyses from in-memory cache."""
        return list(self._analyses.values())

    def get_persisted_findings(
        self, severity: str | None = None, limit: int = 50,
    ) -> list[dict[str, Any]]:
        """Query persisted findings from the persistence backend.

        Strips internal graph ML embedding vectors before returning —
        these are storage implementation details, not domain data.
        """
        _STRIP = {"structural_embedding", "n2v_embedding", "embedding"}
        findings = self._persistence.get_findings(severity=severity, limit=limit)
        return [{k: v for k, v in f.items() if k not in _STRIP} for f in findings]

    def list_persisted_analyses(self, limit: int = 50) -> list[dict[str, Any]]:
        """List analyses from the persistence backend.

        Strips internal graph ML embedding vectors before returning.
        """
        _STRIP = {"structural_embedding", "n2v_embedding", "embedding"}
        analyses = self._persistence.list_analyses(limit=limit)
        return [{k: v for k, v in a.items() if k not in _STRIP} for a in analyses]

    def persistence_health(self) -> dict[str, Any]:
        """Check persistence backend health."""
        return self._persistence.health_check()

    def supported_types(self) -> list[str]:
        """Get supported analysis types."""
        return self._analyzer.supported_types()

    def health_check(self) -> dict[str, Any]:
        """Check runtime health."""
        analyzer_health = self._analyzer.health_check()
        persistence_health = self._persistence.health_check()
        if self._llm:
            llm_health_result = self._llm.health_check()
            llm_health = {
                "available": getattr(llm_health_result, "healthy", False),
                "provider": getattr(llm_health_result, "provider", "unknown"),
            }
        else:
            llm_health = {"available": False}
        return {
            "healthy": analyzer_health.get("healthy", False),
            "analyzer": analyzer_health,
            "persistence": persistence_health,
            "llm": llm_health,
            "analyses_count": len(self._analyses),
        }
