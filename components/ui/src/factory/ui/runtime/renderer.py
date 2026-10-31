import os
from typing import Any, Dict

import yaml
from jinja2 import Environment, FileSystemLoader

from .models import UIView


class Renderer:
    """
    Responsible for loading, templating, and parsing View definitions.
    """

    def __init__(self, config_dir: str):
        self.config_dir = config_dir
        self.views_dir = os.path.join(config_dir, "views")
        # Ensure views directory exists
        if not os.path.exists(self.views_dir):
            os.makedirs(self.views_dir, exist_ok=True)

        self.jinja_env = Environment(
            loader=FileSystemLoader(self.views_dir),
            autoescape=True,
        )

    def render_view(self, view_path: str, context: Dict[str, Any]) -> UIView:
        """
        Loads a view definition, renders it with context, and parses it into a View model.
        view_path: relative path to the view file inside config/views (e.g., "dashboard.yaml")
        """
        if not view_path.endswith(".yaml") and not view_path.endswith(".yml"):
            view_path += ".yaml"

        try:
            template = self.jinja_env.get_template(view_path)
            rendered_yaml = template.render(**context)
            view_dict = yaml.safe_load(rendered_yaml)

            return UIView(**view_dict)
        except Exception as e:
            # In a real app, specific custom exceptions would be better
            raise ValueError(f"Failed to render view '{view_path}': {str(e)}")

    def list_views(self) -> list[str]:
        """
        Lists all available view files.
        """
        views = []
        for root, _, files in os.walk(self.views_dir):
            for file in files:
                if file.endswith(".yaml") or file.endswith(".yml"):
                    rel_path = os.path.relpath(os.path.join(root, file), self.views_dir)
                    views.append(rel_path)
        return views
