"""MCP Prompt registration for Foreman."""

from typing import Any

from .templates import (
    MIGRATE_REPO_TEMPLATE,
    CREATE_COMPONENT_TEMPLATE,
    FIX_COMPLIANCE_TEMPLATE,
    ONBOARD_AGENT_TEMPLATE,
)


def register(mcp: Any) -> None:
    """Register all Foreman prompts with the MCP server."""

    @mcp.prompt()
    def migrate_repo(source_repo_url: str, source_description: str = "") -> str:
        """
        Guided workflow for recreating an external repository as factory-native bricks.
        
        Use this when absorbing/migrating an external project into Python Factory.
        The prompt guides analysis, capability mapping, gap identification, and issue creation.
        """
        repo_name = source_repo_url.split("/")[-1] if "/" in source_repo_url else "unknown"
        project_name = repo_name.lower().replace("-", "_")
        return MIGRATE_REPO_TEMPLATE.format(
            source_repo_url=source_repo_url,
            source_description=source_description or "(No description provided)",
            repo_name=repo_name,
            project_name=project_name,
        )

    @mcp.prompt()
    def create_component(name: str, description: str = "", features: str = "") -> str:
        """Generate guidance for creating a new component brick."""
        features_list = [f.strip() for f in features.split(",") if f.strip()]
        features_yaml = "\n".join(f"  - {f}" for f in features_list) if features_list else "  - core"
        
        return CREATE_COMPONENT_TEMPLATE.format(
            name=name,
            description=description or f"{name} component",
            features=features or "core",
            features_yaml=features_yaml,
        )

    @mcp.prompt()
    def fix_compliance(violations: str = "") -> str:
        """Generate guidance for fixing compliance violations."""
        return FIX_COMPLIANCE_TEMPLATE.format(
            violations=violations or "(Run foreman_guardian_check to see current violations)",
        )

    @mcp.prompt()
    def onboard_agent() -> str:
        """Onboarding guide for agents new to this workspace."""
        return ONBOARD_AGENT_TEMPLATE
