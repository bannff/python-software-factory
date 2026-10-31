"""Persona → strands ``AgentSkills`` vended-plugin projection (issue #104).

Persona ``skills`` are skill-dir ids resolved through the layered skill
store (packaged built-ins + the durable user root, issue #137); the SDK
plugin (``strands.vended_plugins.skills.AgentSkills``) surfaces names and
descriptions to the model and loads full SKILL.md content on demand through
the ``skills`` tool it registers — progressive disclosure lives in the plugin,
never in the persona system prompt.
"""
from __future__ import annotations

import logging
from typing import Any

from factory.mcp_utils.interface import get_service
from ..skill_policy import SkillPolicy
from ..skill_store import read_roots, skill_dir

logger = logging.getLogger(__name__)

_POLICY_SERVICE = "agent_skill_policy_store"


def persona_skills(agent_config: Any, policy: SkillPolicy | None = None) -> list[Any]:
    """Resolve a persona's skill ids into one ``AgentSkills`` plugin.

    Missing dirs are logged and skipped; a non-empty persona list with ZERO
    resolvable dirs fails loudly (misconfiguration, not a skill-less persona).
    """
    from strands.vended_plugins.skills import AgentSkills

    if policy is None:
        store = get_service(_POLICY_SERVICE)
        policy = store.get("", "") if store is not None else SkillPolicy()
    wanted = policy.apply(list(getattr(agent_config, "skills", []) or []))
    if not wanted:
        return []
    dirs = []
    for skill_id in wanted:
        directory = skill_dir(skill_id)
        if directory is None:
            logger.warning("skill_id=<%s> | skill dir missing, skipped", skill_id)
        else:
            dirs.append(str(directory))
    if wanted and not dirs:
        roots = ", ".join(str(root) for root, _builtin in read_roots())
        raise FileNotFoundError(
            f"persona={getattr(agent_config, 'id', '?')} declared skills={wanted} "
            f"but none resolve under {roots}"
        )
    return [AgentSkills(skills=dirs)]


__all__ = ["persona_skills"]
