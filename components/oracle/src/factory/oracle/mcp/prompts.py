"""MCP prompts for the oracle brick — guided verification workflow."""

from __future__ import annotations

from typing import Callable, TYPE_CHECKING

from typing import Any

if TYPE_CHECKING:
    from ..runtime.runtime import OracleRuntime


def register(mcp: Any, get_runtime: Callable[[], "OracleRuntime"]) -> None:
    """Register oracle prompts with the MCP server."""

    @mcp.prompt()
    def verify_finding(finding_id: str, domain: str = "") -> str:
        """Guide an agent through verifying a finding via the oracle."""
        return (
            f"Verify finding '{finding_id}'"
            + (f" for domain '{domain}'" if domain else "")
            + ".\n\n"
            "1. Call oracle_verify_finding(finding_id"
            + (f"='{finding_id}'" if finding_id else "")
            + (f", domain='{domain}'" if domain else "")
            + ").\n"
            "2. Inspect the returned {state, evidence, verifier}.\n"
            "3. The neutral state is persisted atomically on the finding "
            "when it is one of {candidate, verifying, verified, refuted}.\n"
            "If no verifier is registered for the domain, the state is "
            "left unchanged with a 'no verifier registered' note."
        )
