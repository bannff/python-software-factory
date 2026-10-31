"""MCP primitives for integrations brick."""

from factory.integrations.mcp.deterministic import register as register_deterministic
from factory.integrations.mcp.operational import register as register_operational
from factory.integrations.mcp.provider_email import register as register_provider_email
from factory.integrations.mcp.authoring import register as register_authoring
from factory.integrations.mcp.resources import register as register_resources
from factory.integrations.mcp.prompts import register as register_prompts
from .views import register as register_views

__all__ = [
    "register_deterministic",
    "register_operational",
    "register_provider_email",
    "register_authoring",
    "register_resources",
    "register_prompts",
    "register_views",
]
