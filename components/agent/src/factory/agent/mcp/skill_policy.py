"""Owner-scoped Agent skill enablement policy MCP boundary."""
from __future__ import annotations

from typing import Any

from factory.mcp_utils.interface import (
    ToolResult, deterministic, fail, get_envelope, ok, operational,
)

from ..runtime.skill_policy import SkillPolicyStore, StaleSkillPolicy
from .contracts.skill_policy import (
    SkillPolicyGetInput, SkillPolicyOutput, SkillPolicyUpdateInput,
)

_ERROR = "agent_skill_policy_unavailable"


def _authority() -> tuple[str, str]:
    envelope = get_envelope() or {}
    tenant, owner = envelope.get("tenant_id"), envelope.get("principal_id")
    if not isinstance(tenant, str) or not tenant.strip() \
            or not isinstance(owner, str) or not owner.strip():
        raise ValueError(_ERROR)
    return tenant, owner


def register(mcp: Any, store: SkillPolicyStore, known_skill_ids: Any) -> None:
    """``known_skill_ids`` is a callable returning the on-disk skill ids."""
    @mcp.tool()
    @deterministic(input_model=SkillPolicyGetInput, output_model=SkillPolicyOutput)
    def get_skill_policy() -> ToolResult[SkillPolicyOutput]:
        try:
            policy = store.get(*_authority())
            return ok(SkillPolicyOutput(
                disabled_skills=list(policy.disabled_skills), revision=policy.revision,
            ))
        except (OSError, ValueError):
            return fail(_ERROR)

    @mcp.tool()
    @operational(input_model=SkillPolicyUpdateInput, output_model=SkillPolicyOutput)
    def update_skill_policy(
        disabled_skills: list[str], expected_revision: int,
    ) -> ToolResult[SkillPolicyOutput]:
        try:
            known = set(known_skill_ids())
            if any(item not in known for item in disabled_skills):
                return fail("agent_skill_policy_unknown_skill")
            policy = store.update(
                *_authority(), expected_revision,
                disabled_skills=tuple(sorted(disabled_skills)),
            )
            return ok(SkillPolicyOutput(
                disabled_skills=list(policy.disabled_skills), revision=policy.revision,
            ))
        except StaleSkillPolicy:
            return fail("agent_skill_policy_conflict")
        except (OSError, ValueError):
            return fail(_ERROR)


__all__ = ["register"]
