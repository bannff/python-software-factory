"""Exact-tool Artifacts curator persona."""
from __future__ import annotations

from ..runtime.companion.prompt import COMPANION_X_PROMPT
from ..runtime.registry_contracts import AgentConfig

ARTIFACT_CHAT_TOOLS = [
    "artifacts_get", "artifacts_list", "artifacts_versions",
    "artifacts_get_comments", "artifacts_folder_list", "artifacts_save",
    "artifacts_update", "artifacts_revert", "artifacts_tombstone",
    "artifacts_post_comment", "artifacts_reply_comment",
    "artifacts_mark_comment_review", "artifacts_folder_create",
    "artifacts_folder_rename", "artifacts_folder_move",
    "artifacts_folder_delete", "artifacts_move",
]

ARTIFACT_CURATOR_AGENT = AgentConfig(
    id="artifact-curator",
    name="Artifact Curator",
    model="",  # inherit COMPANION_X_CHAT_MODEL — bare "openrouter" broke spawns on non-OpenRouter deployments
    system_prompt=(
        COMPANION_X_PROMPT
        + "\n\nYou organize and iterate versioned artifacts. Use only the supplied "
          "Artifacts tools. Read the current revision before mutations, preserve "
          "history through revert, and mark comments for review rather than resolving them."
    ),
    tools=ARTIFACT_CHAT_TOOLS,
    exact_tools=True,
    skills=[],
    description="Exact-scope assistant for versioning, organizing, and reviewing artifacts.",
)

ARTIFACT_AGENTS = [ARTIFACT_CURATOR_AGENT]

__all__ = ["ARTIFACT_AGENTS", "ARTIFACT_CHAT_TOOLS", "ARTIFACT_CURATOR_AGENT"]
