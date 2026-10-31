"""Template registry and rendering."""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import yaml

from factory.notification.runtime.config import TemplateConfig


class TemplateRegistry:
    """Registry for notification templates loaded from config."""

    def __init__(self, config_dir: Path):
        self.config_dir = Path(config_dir)
        self.templates: dict[str, TemplateConfig] = {}
        self._load_templates()

    def _load_templates(self) -> None:
        """Load templates from config/templates/*.yaml."""
        templates_dir = self.config_dir / "templates"
        if not templates_dir.exists():
            return

        for path in templates_dir.glob("*.yaml"):
            try:
                data = yaml.safe_load(path.read_text())
                if data:
                    template = TemplateConfig.model_validate(data)
                    self.templates[template.id] = template
            except Exception:
                # Skip invalid files
                pass

    def get(self, template_id: str) -> TemplateConfig | None:
        """Get template by ID."""
        return self.templates.get(template_id)

    def as_list(self) -> list[dict[str, Any]]:
        """Return list of template metadata."""
        return [t.as_dict() for t in self.templates.values()]


def render_template(template: TemplateConfig, data: dict[str, Any]) -> dict[str, str]:
    """Render a template with provided data.
    
    Args:
        template: Template configuration
        data: Variables to substitute
        
    Returns:
        Dict with 'subject' and 'body' keys
        
    Raises:
        ValueError: If required variable is missing
    """
    # Check for missing required variables
    for var in template.variables:
        if var not in data:
            raise ValueError(f"Missing required variable: {var}")

    def substitute(text: str | None) -> str:
        if not text:
            return ""
        # Simple {{var}} substitution
        result = text
        for key, value in data.items():
            result = result.replace(f"{{{{{key}}}}}", str(value))
        return result

    return {
        "subject": substitute(template.subject),
        "body": substitute(template.body),
    }
