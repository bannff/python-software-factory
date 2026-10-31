"""Deterministic (read-only) MCP tools for the oracle brick."""

from __future__ import annotations

from typing import Callable, TYPE_CHECKING

from typing import Any
from factory.mcp_utils.registration import typed_tool
from factory.mcp_utils.interface import ToolResult, deterministic, ok

from .contracts import (
    CapabilitiesOutput,
    ConfigSchemaOutput,
    EmptyInput,
    HealthOutput,
    StatesOutput,
    VerifiersOutput,
)

if TYPE_CHECKING:
    from ..runtime.runtime import OracleRuntime


_FEATURES = [
    "finding_verification",
    "verifier_registry_overlay",
    "generic_fallback",
    "domain_agnostic_dispatch",
]


def register(mcp: Any, get_runtime: Callable[[], "OracleRuntime"]) -> None:
    """Register deterministic + contract tools with strict typed boundaries."""

    @typed_tool(mcp)
    @deterministic(input_model=EmptyInput, output_model=CapabilitiesOutput)
    def oracle_get_capabilities() -> ToolResult[CapabilitiesOutput]:
        """Return machine-readable capabilities for the oracle brick."""
        return ok(CapabilitiesOutput(name="oracle", version="1.0.0", features=_FEATURES))

    @typed_tool(mcp)
    @deterministic(input_model=EmptyInput, output_model=HealthOutput)
    def oracle_health_check() -> ToolResult[HealthOutput]:
        """Fast readiness probe — reports registered verifier count."""
        return ok(HealthOutput(healthy=True, verifiers=len(get_runtime().registry.domains())))

    @typed_tool(mcp)
    @deterministic(input_model=EmptyInput, output_model=ConfigSchemaOutput)
    def oracle_describe_config_schema() -> ToolResult[ConfigSchemaOutput]:
        """Describe oracle configuration schema (no config today)."""
        return ok(ConfigSchemaOutput(
            type="object", additional_properties=False, properties={},
        ))

    @typed_tool(mcp)
    @deterministic(input_model=EmptyInput, output_model=VerifiersOutput)
    def oracle_list_verifiers() -> ToolResult[VerifiersOutput]:
        """List registered verifier domains (built-ins + pack overlay)."""
        domains = get_runtime().registry.domains()
        return ok(VerifiersOutput(domains=domains, count=len(domains)))

    @typed_tool(mcp)
    @deterministic(input_model=EmptyInput, output_model=StatesOutput)
    def oracle_list_states() -> ToolResult[StatesOutput]:
        """List the closed neutral verification-state set."""
        from ..core import FINDING_STATES
        return ok(StatesOutput(states=sorted(FINDING_STATES)))
