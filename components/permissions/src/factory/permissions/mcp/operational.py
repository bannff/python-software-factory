"""Strict typed operational tools for the Permissions brick."""
from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING

from typing import Any

from factory.mcp_utils.interface import ToolResult, get_envelope, ok, operational
from factory.mcp_utils.registration import typed_tool
from factory.permissions.runtime.envelope import Envelope

from .contracts import (
    BatchEvaluateInput, BatchEvaluateOutput, DecisionOutput, EnvelopeInput, EvaluateInput,
    ExplainOutput, Identifier, JsonObject, PermissionRequestInput, ResourceInput,
)
from .evidence import normalize_policy_evidence, normalize_provider_issues

if TYPE_CHECKING:
    from factory.permissions.runtime.runtime import PermissionsRuntime

_TRUSTED_FIELDS = frozenset({
    "session_id", "request_id", "correlation_id", "agent_id", "tool_name", "attributes",
})
_IDENTITY_FIELDS = ("principal_id", "tenant_id")


def _runtime_envelope(value: JsonObject | EnvelopeInput | None) -> Envelope:
    """Validate public input first, then apply trusted context authority."""
    public = value if isinstance(value, EnvelopeInput) else EnvelopeInput.model_validate(value or {})
    payload = public.model_dump(exclude_none=True)
    trusted = get_envelope()
    if trusted is None:
        return Envelope.model_validate(payload)
    if not isinstance(trusted, Mapping):
        raise ValueError("invalid trusted envelope")
    for key in _IDENTITY_FIELDS:
        if key in trusted:
            payload[key] = trusted[key]
        else:
            payload.pop(key, None)
    for key in _TRUSTED_FIELDS:
        if key in trusted:
            payload[key] = trusted[key]
    return Envelope.model_validate(payload)


def _mapping(result: object) -> Mapping[str, object]:
    if not isinstance(result, Mapping):
        raise ValueError("runtime result must be a mapping")
    return result


def _decision_output(result: Mapping[str, object]) -> DecisionOutput:
    result = _mapping(result)
    fields: dict[str, object] = {
        key: result[key]
        for key in ("decision", "reason", "policy_id", "rule_id", "obligations")
        if key in result
    }
    if "determining_policies" in result:
        fields["determining_policies"] = normalize_policy_evidence(
            result["determining_policies"], "determining_policies",
        )
    if "diagnostics" in result:
        fields["diagnostics"] = normalize_provider_issues(result["diagnostics"], "diagnostics")
    if "errors" in result:
        fields["errors"] = normalize_provider_issues(result["errors"], "errors")
    return DecisionOutput.model_validate(fields)


def _explain_output(result: Mapping[str, object]) -> ExplainOutput:
    result = _mapping(result)
    fields: dict[str, object] = {
        key: result[key]
        for key in ("decision", "reason", "trace_id", "obligations")
        if key in result
    }
    if "matched_rules" in result:
        fields["matched_rules"] = normalize_policy_evidence(result["matched_rules"], "matched_rules")
    if "determining_policies" in result:
        fields["determining_policies"] = normalize_policy_evidence(
            result["determining_policies"], "determining_policies",
        )
    if "diagnostics" in result:
        fields["diagnostics"] = normalize_provider_issues(result["diagnostics"], "diagnostics")
    if "errors" in result:
        fields["errors"] = normalize_provider_issues(result["errors"], "errors")
    return ExplainOutput.model_validate(fields)


def register(mcp: Any, runtime: "PermissionsRuntime") -> None:
    """Register evaluate, batch_evaluate, and explain with strict ingress."""

    @typed_tool(mcp, name="permissions.evaluate")
    @operational(input_model=EvaluateInput, output_model=DecisionOutput)
    def evaluate(
        action: Identifier,
        resource: ResourceInput,
        context: JsonObject | None = None,
        envelope: EnvelopeInput | None = None,
    ) -> ToolResult[DecisionOutput]:
        """Evaluate one permission request and return allow/deny data."""
        result = runtime.evaluate(
            action=action, resource=resource, context=context or {}, envelope=_runtime_envelope(envelope),
        )
        return ok(_decision_output(result))

    @typed_tool(mcp, name="permissions.batch_evaluate")
    @operational(input_model=BatchEvaluateInput, output_model=BatchEvaluateOutput)
    def batch_evaluate(
        requests: list[PermissionRequestInput], envelope: EnvelopeInput | None = None,
    ) -> ToolResult[BatchEvaluateOutput]:
        """Evaluate requests in input order while preserving per-item audit logs."""
        result = runtime.batch_evaluate(requests=requests, envelope=_runtime_envelope(envelope))
        if not isinstance(result, list):
            raise ValueError("runtime batch result must be a list")
        decisions = [_decision_output(item) for item in result]
        return ok(BatchEvaluateOutput(decisions=decisions, count=len(decisions)))

    @typed_tool(mcp, name="permissions.explain")
    @operational(input_model=EvaluateInput, output_model=ExplainOutput)
    def explain(
        action: Identifier,
        resource: ResourceInput,
        context: JsonObject | None = None,
        envelope: EnvelopeInput | None = None,
    ) -> ToolResult[ExplainOutput]:
        """Explain the policy decision with bounded matching evidence."""
        result = runtime.explain(
            action=action, resource=resource, context=context or {}, envelope=_runtime_envelope(envelope),
        )
        return ok(_explain_output(result))


__all__ = ["register"]
