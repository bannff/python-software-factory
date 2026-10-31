"""A2UI JSON schema and validation.

Defines the A2UI payload structure and validates agent-generated UI.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class A2UIComponent:
    """A single A2UI component from agent payload."""

    id: str
    type: str
    props: dict[str, Any] = field(default_factory=dict)
    parent: str | None = None
    children: list[str] = field(default_factory=list)
    data_model: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "A2UIComponent":
        """Create from dictionary."""
        return cls(
            id=data.get("id", ""),
            type=data.get("type", ""),
            props=data.get("props", {}),
            parent=data.get("parent"),
            children=data.get("children", []),
            data_model=data.get("dataModel", {}),
        )

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        result: dict[str, Any] = {"id": self.id, "type": self.type}
        if self.props:
            result["props"] = self.props
        if self.parent:
            result["parent"] = self.parent
        if self.children:
            result["children"] = self.children
        if self.data_model:
            result["dataModel"] = self.data_model
        return result


@dataclass
class A2UIPayload:
    """Complete A2UI payload from agent."""

    components: list[A2UIComponent] = field(default_factory=list)
    version: str = "0.8"
    metadata: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "A2UIPayload":
        """Create from dictionary."""
        components = [
            A2UIComponent.from_dict(c) for c in data.get("components", [])
        ]
        return cls(
            components=components,
            version=data.get("version", "0.8"),
            metadata=data.get("metadata", {}),
        )

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "components": [c.to_dict() for c in self.components],
            "version": self.version,
            "metadata": self.metadata,
        }


@dataclass
class ValidationError:
    """A validation error in A2UI payload."""

    path: str
    message: str
    component_id: str | None = None


def validate_a2ui(payload: dict[str, Any]) -> list[ValidationError]:
    """Validate A2UI payload structure.

    Returns list of validation errors (empty if valid).
    """
    errors: list[ValidationError] = []

    # Check required fields
    if "components" not in payload:
        errors.append(ValidationError("root", "Missing 'components' array"))
        return errors

    if not isinstance(payload["components"], list):
        errors.append(ValidationError("components", "Must be an array"))
        return errors

    # Validate each component
    seen_ids: set[str] = set()
    for i, comp in enumerate(payload["components"]):
        path = f"components[{i}]"

        if not isinstance(comp, dict):
            errors.append(ValidationError(path, "Component must be an object"))
            continue

        # Required: id
        if "id" not in comp:
            errors.append(ValidationError(path, "Missing required 'id'"))
        elif not isinstance(comp["id"], str):
            errors.append(ValidationError(path, "'id' must be a string"))
        elif comp["id"] in seen_ids:
            errors.append(ValidationError(
                path, f"Duplicate id: {comp['id']}", comp["id"]
            ))
        else:
            seen_ids.add(comp["id"])

        # Required: type
        if "type" not in comp:
            errors.append(ValidationError(
                path, "Missing required 'type'", comp.get("id")
            ))
        elif not isinstance(comp["type"], str):
            errors.append(ValidationError(
                path, "'type' must be a string", comp.get("id")
            ))

        # Optional: props must be object
        if "props" in comp and not isinstance(comp["props"], dict):
            errors.append(ValidationError(
                path, "'props' must be an object", comp.get("id")
            ))

        # Optional: parent must reference existing id
        if "parent" in comp:
            parent_id = comp["parent"]
            if not isinstance(parent_id, str):
                errors.append(ValidationError(
                    path, "'parent' must be a string", comp.get("id")
                ))

    # Validate parent references (second pass)
    for comp in payload["components"]:
        if isinstance(comp, dict) and "parent" in comp:
            if comp["parent"] not in seen_ids:
                errors.append(ValidationError(
                    f"components[id={comp.get('id')}]",
                    f"Parent '{comp['parent']}' not found",
                    comp.get("id"),
                ))

    return errors
