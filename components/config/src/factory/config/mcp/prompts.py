"""MCP Prompt registration for Config brick.

Prompts provide guided workflows for common tasks:
- Setting up configuration sources
- Adding feature flags
- Debugging configuration issues
- Migrating between sources
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Callable

from typing import Any

from .templates import PROMPT_TEMPLATES
from .backend_guides import BACKEND_GUIDES

if TYPE_CHECKING:
    from ..runtime.runtime import ConfigRuntime


def register(mcp: Any, get_runtime: Callable[[], "ConfigRuntime"]) -> None:
    """Register all Config prompts with the MCP server."""

    @mcp.prompt()
    def configure_source(backend: str = "env") -> str:
        """Generate guidance for setting up a configuration source."""
        runtime = get_runtime()
        backend = backend.lower()
        if backend not in BACKEND_GUIDES:
            backend = "env"

        guide = BACKEND_GUIDES[backend]
        return PROMPT_TEMPLATES["configure_source"]["template"].format(
            backend=backend,
            environment=runtime.environment,
            setup_guide=guide["setup_guide"],
            backend_config=guide["backend_config"],
        )

    @mcp.prompt()
    def add_feature_flag(
        flag_name: str,
        purpose: str = "",
        default_enabled: bool = False,
        rollout_percentage: int = 0,
    ) -> str:
        """Generate guidance for adding a new feature flag."""
        flag_id = flag_name.lower().replace(" ", "_").replace("-", "_")
        return PROMPT_TEMPLATES["add_feature_flag"]["template"].format(
            flag_name=flag_id,
            purpose=purpose or f"Control {flag_name} feature",
            default_enabled=str(default_enabled).lower(),
            rollout_percentage=rollout_percentage,
        )

    @mcp.prompt()
    def debug_config(
        key: str = "",
        prefix: str = "",
        issue: str = "",
    ) -> str:
        """Generate guidance for debugging configuration issues."""
        return PROMPT_TEMPLATES["debug_config"]["template"].format(
            key=key or "your.config.key",
            prefix=prefix or "",
            issue=issue or "Configuration value not as expected",
        )

    @mcp.prompt()
    def migrate_config(
        source_backend: str = "env",
        target_backend: str = "file",
    ) -> str:
        """Generate guidance for migrating between configuration sources."""
        source = source_backend.lower()
        target = target_backend.lower()

        # Get target setup guide
        target_guide = BACKEND_GUIDES.get(target, BACKEND_GUIDES["file"])
        target_setup = target_guide["setup_guide"] + "\n" + target_guide["backend_config"]

        return PROMPT_TEMPLATES["migrate_config"]["template"].format(
            source_backend=source,
            target_backend=target,
            target_setup=target_setup,
        )
