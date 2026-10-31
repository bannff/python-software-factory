"""Typed Agent skill discovery, reading, and per-action gated authoring."""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from factory.mcp_utils.interface import (
    ToolResult, authoring, deterministic, fail, ok,
)

from ..authoring import AuthoringRootUnavailable, gated_tool, policy_for
from ..runtime.skill_store import (
    BuiltinSkillError, StoredSkill, add_skill, delete_skill, list_skills, read_skill,
)
from .contracts.discovery import (
    EmptyInput, SkillAddInput, SkillAddOutput, SkillDeleteOutput,
    SkillDetailOutput, SkillIdInput, SkillSummary, SkillsOutput,
)

if TYPE_CHECKING:
    from ..agent import SuperAgent

logger = logging.getLogger(__name__)


def _summary(skill: StoredSkill) -> SkillSummary:
    return SkillSummary(id=skill.id, name=skill.name, description=skill.description)


def register(mcp: Any, agent: "SuperAgent") -> None:
    """Register always-readable skills and explicitly gated creation."""
    policy = policy_for(agent)

    @mcp.tool()
    @deterministic(input_model=EmptyInput, output_model=SkillsOutput)
    def agent_list_skills() -> ToolResult[SkillsOutput]:
        skills = [_summary(skill) for skill in list_skills()]
        return ok(SkillsOutput(count=len(skills), skills=skills))

    @mcp.tool()
    @deterministic(input_model=SkillIdInput, output_model=SkillDetailOutput)
    def agent_read_skill(skill_id: str) -> ToolResult[SkillDetailOutput]:
        stored = read_skill(skill_id)
        if stored is None:
            return fail("skill_not_found")
        skill, body = stored
        return ok(SkillDetailOutput(**_summary(skill).model_dump(), body=body))

    @gated_tool(mcp, policy, "skills", "add")
    @authoring(input_model=SkillAddInput, output_model=SkillAddOutput)
    def agent_add_skill(
        skill_id: str, name: str, description: str, body: str,
    ) -> ToolResult[SkillAddOutput]:
        try:
            skill = add_skill(skill_id, name, description, body)
        except FileExistsError:
            return fail("skill_exists")
        except AuthoringRootUnavailable as error:
            logger.warning("authoring root unavailable: %s", error)
            return fail("authoring_root_unavailable")
        except (OSError, ValueError):
            return fail("skill_write_failed")
        return ok(SkillAddOutput(created=True, skill=_summary(skill)))

    @gated_tool(mcp, policy, "skills", "delete")
    @authoring(input_model=SkillIdInput, output_model=SkillDeleteOutput)
    def agent_delete_skill(skill_id: str) -> ToolResult[SkillDeleteOutput]:
        try:
            deleted = delete_skill(skill_id)
        except BuiltinSkillError:
            return fail("cannot_delete_builtin")
        except AuthoringRootUnavailable as error:
            logger.warning("authoring root unavailable: %s", error)
            return fail("authoring_root_unavailable")
        except OSError:
            return fail("skill_write_failed")
        if not deleted:
            return fail("skill_not_found")
        return ok(SkillDeleteOutput(deleted=True, skill_id=skill_id))


__all__ = ["register"]
