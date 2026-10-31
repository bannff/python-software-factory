"""MCP prompts for the public dataset job workflow."""

from typing import Any


def register(mcp: Any) -> None:
    """Register a concise recipe-submission prompt."""

    @mcp.prompt()
    def prepare_dataset_generation(recipe_uri: str, recipe_digest: str) -> str:
        """Prepare an immutable request before submitting a dataset job."""
        return (
            "Submit dataset_submit_generation with recipe_uri="
            f"{recipe_uri!r}, recipe_digest={recipe_digest!r}, immutable input artifact "
            "URIs and SHA-256 digests. Poll dataset_get_job; resolve completion with "
            "dataset_get_artifact then dataset_resolve_artifact."
        )