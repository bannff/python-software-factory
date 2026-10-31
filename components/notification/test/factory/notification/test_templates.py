"""Tests for template rendering."""
from __future__ import annotations

import pytest
from pathlib import Path

from factory.notification.runtime.templates import TemplateRegistry, render_template


def _create_template_config(tmp_path: Path) -> Path:
    """Create test template config."""
    cfg = tmp_path / "config"
    templates_dir = cfg / "templates"
    templates_dir.mkdir(parents=True)
    
    (templates_dir / "welcome.yaml").write_text("""
id: welcome
name: Welcome Email
subject: "Welcome, {{name}}!"
body: |
  Hello {{name}},
  
  Welcome to {{service}}!
  
  Best regards,
  The Team
variables:
  - name
  - service
""")
    
    (templates_dir / "alert.yaml").write_text("""
id: alert
name: Alert Notification
subject: "[{{severity}}] {{title}}"
body: "Alert: {{message}}"
variables:
  - severity
  - title
  - message
""")
    
    return cfg


class TestTemplateRegistry:
    """Test template registry loading."""

    def test_loads_templates_from_config(self, tmp_path: Path) -> None:
        """Should load templates from config/templates/*.yaml."""
        cfg = _create_template_config(tmp_path)
        registry = TemplateRegistry(cfg)
        
        templates = registry.as_list()
        assert len(templates) == 2
        
        ids = [t["id"] for t in templates]
        assert "welcome" in ids
        assert "alert" in ids

    def test_get_template_by_id(self, tmp_path: Path) -> None:
        """Should retrieve template by ID."""
        cfg = _create_template_config(tmp_path)
        registry = TemplateRegistry(cfg)
        
        template = registry.get("welcome")
        assert template is not None
        assert template.name == "Welcome Email"
        assert "name" in template.variables

    def test_get_nonexistent_template(self, tmp_path: Path) -> None:
        """Should return None for nonexistent template."""
        cfg = _create_template_config(tmp_path)
        registry = TemplateRegistry(cfg)
        
        template = registry.get("nonexistent")
        assert template is None


class TestRenderTemplate:
    """Test template rendering."""

    def test_renders_variables(self, tmp_path: Path) -> None:
        """Should substitute variables in template."""
        cfg = _create_template_config(tmp_path)
        registry = TemplateRegistry(cfg)
        template = registry.get("welcome")
        
        result = render_template(template, {"name": "Alice", "service": "MyApp"})
        
        assert "Alice" in result["body"]
        assert "MyApp" in result["body"]
        assert result["subject"] == "Welcome, Alice!"

    def test_renders_alert_template(self, tmp_path: Path) -> None:
        """Should render alert template."""
        cfg = _create_template_config(tmp_path)
        registry = TemplateRegistry(cfg)
        template = registry.get("alert")
        
        result = render_template(template, {
            "severity": "HIGH",
            "title": "CPU Spike",
            "message": "CPU usage exceeded 90%"
        })
        
        assert result["subject"] == "[HIGH] CPU Spike"
        assert "CPU usage exceeded 90%" in result["body"]

    def test_missing_variable_raises(self, tmp_path: Path) -> None:
        """Should raise error for missing required variable."""
        cfg = _create_template_config(tmp_path)
        registry = TemplateRegistry(cfg)
        template = registry.get("welcome")
        
        with pytest.raises(ValueError, match="Missing.*name"):
            render_template(template, {"service": "MyApp"})  # missing 'name'
