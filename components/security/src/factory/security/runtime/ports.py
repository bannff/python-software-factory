"""Protocol interfaces for security adapters."""

from typing import Any, Protocol


class SecurityAnalyzerPort(Protocol):
    """Protocol for security analysis backends."""

    async def analyze(
        self, target: str, analysis_type: str, options: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        """Run security analysis on target, return findings."""
        ...

    async def get_analysis_status(self, analysis_id: str) -> dict[str, Any]:
        """Get status of running analysis."""
        ...

    async def cancel_analysis(self, analysis_id: str) -> None:
        """Cancel a running analysis."""
        ...

    def supported_types(self) -> list[str]:
        """Return list of supported analysis types."""
        ...

    def health_check(self) -> dict[str, Any]:
        """Check adapter health."""
        ...


class FindingPersistencePort(Protocol):
    """Protocol for persisting security findings and analyses.

    Implementations store SecurityAction, Finding, and relationship
    data per the security taxonomy (graph://schemas/security-taxonomy).
    """

    def persist_analysis(
        self, analysis_id: str, analysis_type: str, target: str,
        findings: list[dict[str, Any]], summary: str | None = None,
    ) -> dict[str, Any]:
        """Persist an analysis and its findings. Returns persistence result."""
        ...

    def get_analysis(self, analysis_id: str) -> dict[str, Any] | None:
        """Retrieve a persisted analysis by ID."""
        ...

    def list_analyses(self, limit: int = 50) -> list[dict[str, Any]]:
        """List persisted analyses."""
        ...

    def get_findings(
        self, severity: str | None = None, limit: int = 50,
    ) -> list[dict[str, Any]]:
        """Query persisted findings, optionally filtered by severity."""
        ...

    def health_check(self) -> dict[str, Any]:
        """Check persistence backend health."""
        ...


# -- Pentest adapter port --------------------------------------------------

from enum import Enum
from pydantic import BaseModel, Field


class ScanType(str, Enum):
    """Supported pentest scan types."""
    port_scan = "port_scan"
    vuln_scan = "vuln_scan"
    web_fuzz = "web_fuzz"
    sql_inject = "sql_inject"
    http_probe = "http_probe"
    nuclei_scan = "nuclei_scan"


class ScanJob(BaseModel):
    """Represents a launched pentest scan job."""
    job_id: str
    scan_type: ScanType
    target: str
    status: str = "pending"  # pending, running, completed, failed, cancelled
    started_at: str = ""
    env_id: str | None = None


class ScanResults(BaseModel):
    """Parsed results from a completed scan."""
    job_id: str
    scan_type: ScanType
    raw_output: str = ""
    findings: list[dict[str, Any]] = Field(default_factory=list)
    duration_ms: int = 0
    exit_code: int = 0


class PentestPort(Protocol):
    """Protocol for pentest tool backends (same pattern as all bricks)."""

    async def scan(
        self, scan_type: ScanType, target: str,
        options: dict[str, Any] | None = None,
    ) -> ScanJob: ...

    async def get_status(self, job_id: str) -> dict[str, Any]: ...

    async def get_results(self, job_id: str) -> ScanResults: ...

    async def cancel(self, job_id: str) -> bool: ...

    async def list_jobs(self) -> list[ScanJob]: ...

    async def cleanup(self) -> None: ...
