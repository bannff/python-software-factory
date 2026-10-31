"""Owner-scoped Agent tool approval policy MCP boundary."""
from __future__ import annotations

from typing import Any

from factory.mcp_utils.interface import (
    ToolResult, deterministic, get_envelope, ok, operational, fail,
)

from .contracts.approval_policy import (
    ApprovalPolicyGetInput, ApprovalPolicyOutput, ApprovalPolicyUpdateInput,
)
from ..runtime.approval_policy import ApprovalPolicyStore, StaleApprovalPolicy

_ERROR = "agent_approval_unavailable"


def _authority() -> tuple[str, str]:
    envelope = get_envelope() or {}
    tenant = envelope.get("tenant_id")
    owner = envelope.get("principal_id")
    if not isinstance(tenant, str) or not tenant.strip() \
            or not isinstance(owner, str) or not owner.strip():
        raise ValueError(_ERROR)
    return tenant, owner


def register(
    mcp: Any, store: ApprovalPolicyStore,
    resolve_names: Any | None = None,
) -> None:
    normalize = resolve_names or (lambda names: tuple(names))
    @mcp.tool()
    @deterministic(input_model=ApprovalPolicyGetInput, output_model=ApprovalPolicyOutput)
    def get_approval_policy() -> ToolResult[ApprovalPolicyOutput]:
        try:
            policy = store.get(*_authority())
            return ok(ApprovalPolicyOutput(
                tool_names=list(policy.tool_names), revision=policy.revision,
            ))
        except (OSError, ValueError):
            return fail(_ERROR)

    @mcp.tool()
    @operational(input_model=ApprovalPolicyUpdateInput, output_model=ApprovalPolicyOutput)
    def update_approval_policy(
        tool_names: list[str], expected_revision: int,
    ) -> ToolResult[ApprovalPolicyOutput]:
        parsed = ApprovalPolicyUpdateInput(
            tool_names=tool_names, expected_revision=expected_revision,
        )
        try:
            canonical = tuple(sorted(normalize(parsed.tool_names)))
            if len(canonical) != len(parsed.tool_names):
                return fail("agent_approval_unknown_tool")
            policy = store.update(
                *_authority(), parsed.expected_revision,
                tool_names=canonical,
            )
            return ok(ApprovalPolicyOutput(
                tool_names=list(policy.tool_names), revision=policy.revision,
            ))
        except StaleApprovalPolicy:
            return fail("agent_approval_conflict")
        except (OSError, ValueError):
            return fail(_ERROR)


__all__ = ["register"]
