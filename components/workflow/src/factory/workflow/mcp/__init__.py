"""MCP primitives for the Workflow brick."""

from . import authoring, deterministic, execution, operational, prompts, resources
from .prompts import register as register_prompts
from .resources import register as register_resources
from .views import register as register_views

__all__ = [
    "authoring", "deterministic", "execution", "operational", "prompts",
    "resources", "register_prompts", "register_resources", "register_views",
]
