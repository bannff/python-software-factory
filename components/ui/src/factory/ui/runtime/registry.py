"""Component registry for managing UI component definitions."""

from typing import Any

from .models import ComponentType, UIComponent
from .registry_models import ComponentDefinition
from .registry_builtins import get_builtin_components

# Re-export for backwards compatibility
__all__ = ["ComponentDefinition", "ComponentRegistry"]


class ComponentRegistry:
    """Registry for UI component definitions."""

    def __init__(self) -> None:
        self._components: dict[ComponentType, ComponentDefinition] = {}
        self._register_builtins()

    def _register_builtins(self) -> None:
        for defn in get_builtin_components():
            self._components[defn.component_type] = defn

    def register(self, definition: ComponentDefinition) -> None:
        self._components[definition.component_type] = definition

    def get(self, component_type: ComponentType) -> ComponentDefinition | None:
        return self._components.get(component_type)

    def list_components(self) -> list[ComponentDefinition]:
        return list(self._components.values())

    def create_component(
        self, component_id: str, component_type: ComponentType,
        props: dict[str, Any] | None = None, styles: dict[str, str] | None = None,
    ) -> UIComponent:
        defn = self._components.get(component_type)
        merged_props = {**(defn.default_props if defn else {})}
        merged_styles = {**(defn.default_styles if defn else {})}

        if props:
            merged_props.update(props)
        if styles:
            merged_styles.update(styles)

        return UIComponent(
            id=component_id, component_type=component_type,
            props=merged_props, styles=merged_styles,
        )

    def to_dict(self) -> dict[str, Any]:
        return {"components": [d.to_dict() for d in self._components.values()]}
