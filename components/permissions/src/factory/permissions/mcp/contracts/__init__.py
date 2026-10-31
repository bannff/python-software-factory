"""Same-brick Pydantic v2 transport DTOs for Permissions MCP tools."""
from .authoring import (
    AuthoringStatusOutput, DeletePolicyOutput, PolicyIdInput, PolicyValidationIssue,
    UpsertPolicyInput, UpsertPolicyOutput, ValidatePoliciesOutput, ValidationDetailOutput,
)
from .base import EmptyInput, Identifier, JsonArray, JsonObject, OutputModel, StrictModel
from .deterministic import (
    CapabilitiesOutput, ConfigSchemaOutput, HealthOutput, PolicyRegistryOutput, PolicySummary,
    RoleRegistryOutput, RoleSummary, ToolCatalog,
)
from .operational import (
    BatchEvaluateInput, BatchEvaluateOutput, DecisionOutput, EnvelopeInput, EvaluateInput,
    ExplainOutput, MatchedRuleOutput, PermissionRequestInput, PolicyEvidenceOutput,
    ProviderDiagnosticOutput, ProviderErrorOutput, ResourceInput,
)

__all__ = [
    "AuthoringStatusOutput", "BatchEvaluateInput", "BatchEvaluateOutput", "CapabilitiesOutput",
    "ConfigSchemaOutput", "DecisionOutput", "DeletePolicyOutput", "EmptyInput", "EnvelopeInput",
    "EvaluateInput", "ExplainOutput", "HealthOutput", "Identifier", "JsonArray", "JsonObject",
    "MatchedRuleOutput", "OutputModel", "PermissionRequestInput", "PolicyEvidenceOutput",
    "PolicyIdInput", "PolicyRegistryOutput", "PolicySummary", "PolicyValidationIssue",
    "ProviderDiagnosticOutput", "ProviderErrorOutput", "ResourceInput", "RoleRegistryOutput",
    "RoleSummary", "StrictModel", "ToolCatalog", "UpsertPolicyInput", "UpsertPolicyOutput",
    "ValidatePoliciesOutput", "ValidationDetailOutput",
]
