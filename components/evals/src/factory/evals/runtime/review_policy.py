"""Frozen built-in review policy specifications for development gates."""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

REVIEW_TOOL_SCOPE = (
    "devtools_read_file", "devtools_list_dir", "devtools_search",
    "devtools_git_status", "devtools_git_diff", "devtools_git_log",
)


class ReviewPolicy(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)
    schema_version: Literal[1] = 1
    policy_id: Literal["review-qa", "review-meta"]
    rubric: str = Field(min_length=1, max_length=8000)
    evaluator_names: tuple[str, ...] = Field(min_length=1, max_length=20)
    min_pass_rate: float = Field(ge=0.0, le=1.0)
    min_avg_score: float = Field(ge=0.0, le=1.0)
    allowed_tool_scope: tuple[str, ...]


_POLICIES = {
    "review-qa": ReviewPolicy(
        policy_id="review-qa",
        rubric=("Evaluate fixed acceptance criteria, behavior, edge cases, "
                "strict typed contracts, and test evidence. Return concise "
                "evidence-backed criterion rows without changing criteria."),
        evaluator_names=("goal_success", "tool_selection"),
        min_pass_rate=0.8, min_avg_score=0.75,
        allowed_tool_scope=REVIEW_TOOL_SCOPE,
    ),
    "review-meta": ReviewPolicy(
        policy_id="review-meta",
        rubric=("Evaluate Polylith ownership, MCP taxonomy, strict ingress and "
                "typed egress, SDK-first reuse, simplicity, and source-size "
                "limits. Return evidence-backed rows without changing criteria."),
        evaluator_names=("goal_success", "helpfulness"),
        min_pass_rate=0.8, min_avg_score=0.75,
        allowed_tool_scope=REVIEW_TOOL_SCOPE,
    ),
}


def get_review_policy(policy_id: str) -> ReviewPolicy:
    try:
        return _POLICIES[policy_id]
    except KeyError as exc:
        raise ValueError("unknown review policy") from exc


def list_review_policies() -> tuple[ReviewPolicy, ...]:
    return tuple(_POLICIES.values())


__all__ = [
    "REVIEW_TOOL_SCOPE", "ReviewPolicy", "get_review_policy", "list_review_policies",
]
