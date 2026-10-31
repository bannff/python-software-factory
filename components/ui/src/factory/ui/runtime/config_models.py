"""Configuration models for UI module."""

from dataclasses import dataclass, field
from typing import Any

from .models import ComponentType, UIComponent, UIView


@dataclass
class UISettings:
    """UI module settings loaded from config/settings.yaml."""
    authoring_enabled: bool = False
    push_enabled: bool = True
    max_clients: int = 100
    storage_backend: str = "memory"
    storage_path: str | None = None
    default_adapter: str = "json"
    enabled_adapters: list[str] = field(default_factory=lambda: ["json", "inline-html"])
    max_views: int = 1000
    max_components_per_view: int = 100
    max_history_entries: int = 1000
    feature_flags: dict[str, bool] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "UISettings":
        return cls(
            authoring_enabled=data.get("authoring_enabled", False),
            push_enabled=data.get("push_enabled", True),
            max_clients=data.get("max_clients", 100),
            storage_backend=data.get("storage_backend", "memory"),
            storage_path=data.get("storage_path"),
            default_adapter=data.get("default_adapter", "json"),
            enabled_adapters=data.get("enabled_adapters", ["json", "inline-html"]),
            max_views=data.get("max_views", 1000),
            max_components_per_view=data.get("max_components_per_view", 100),
            max_history_entries=data.get("max_history_entries", 1000),
            feature_flags=data.get("feature_flags", {}),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "authoring_enabled": self.authoring_enabled,
            "push_enabled": self.push_enabled,
            "max_clients": self.max_clients,
            "storage_backend": self.storage_backend,
            "storage_path": self.storage_path,
            "default_adapter": self.default_adapter,
            "enabled_adapters": self.enabled_adapters,
            "max_views": self.max_views,
            "max_components_per_view": self.max_components_per_view,
            "max_history_entries": self.max_history_entries,
            "feature_flags": self.feature_flags,
        }


@dataclass
class ViewDefinition:
    """A view definition loaded from config/views/*.yaml."""
    id: str
    name: str
    description: str = ""
    layout: dict[str, Any] = field(default_factory=dict)
    components: list[dict[str, Any]] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    tags: list[str] = field(default_factory=list)

    def to_view(self) -> UIView:
        components = []
        for i, comp_def in enumerate(self.components):
            component = UIComponent(
                id=comp_def.get("id", f"{self.id}-comp-{i}"),
                component_type=ComponentType(comp_def.get("type", "text")),
                props=comp_def.get("props", {}),
                styles=comp_def.get("styles", {}),
            )
            components.append(component)

        return UIView(
            id=self.id, name=self.name, components=components, layout=self.layout,
            metadata={**self.metadata, "description": self.description, "tags": self.tags},
        )
