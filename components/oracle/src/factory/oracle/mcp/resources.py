"""MCP resources for the oracle brick — schemas + docs."""

from __future__ import annotations

import json
from typing import Callable, TYPE_CHECKING

from typing import Any

if TYPE_CHECKING:
    from ..runtime.runtime import OracleRuntime

_VERIFY_RESULT_SCHEMA = {
    "type": "object",
    "required": ["state", "verifier"],
    "properties": {
        "state": {
            "type": "string",
            "enum": ["candidate", "verifying", "verified", "refuted"],
            "description": "Closed neutral verification state.",
        },
        "evidence": {
            "description": "Free-form note or structured evidence dict.",
        },
        "verifier": {
            "type": "string",
            "description": "Name of the verifier that produced the outcome.",
        },
    },
}

_DOC = (
    "# Oracle brick\n\n"
    "Thin, domain-agnostic verification oracle. `oracle_verify_finding` "
    "fetches a finding from the graph, dispatches to a registry-resolved "
    "verifier (generic fallback on miss), and persists the neutral state "
    "via the graph brick's atomic `graph_set_finding_state` write.\n\n"
    "Domain verifiers are pure DATA registered through "
    "`factory.oracle.interface.register_verifier` — the engine never "
    "branches on a domain literal.\n"
)


def register(mcp: Any, get_runtime: Callable[[], "OracleRuntime"]) -> None:
    """Register oracle resources with the MCP server."""

    @mcp.resource("oracle://schemas/verify-result")
    def verify_result_schema() -> str:
        """JSON schema for a verifier outcome."""
        return json.dumps(_VERIFY_RESULT_SCHEMA, indent=2)

    @mcp.resource("oracle://docs/oracle")
    def oracle_doc() -> str:
        """Human-readable overview of the oracle brick."""
        return _DOC
