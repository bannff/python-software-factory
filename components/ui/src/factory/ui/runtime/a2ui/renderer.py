"""A2UI to native UI renderer.

Transforms A2UI payloads into native UIView/UIComponent structures.
"""

from __future__ import annotations

import uuid
from typing import Any

from ..models import UIComponent, UIView, ComponentType
from .schema import A2UIPayload, A2UIComponent
from .components import COMPONENT_CATALOG, ComponentSpec


class A2UIParser:
    """Parser for A2UI payloads."""

    @staticmethod
    def parse(payload: dict[str, Any]) -> A2UIPayload:
        """Parse raw A2UI payload into structured format."""
        return A2UIPayload.from_dict(payload)

    @staticmethod
    def build_tree(payload: A2UIPayload) -> list[A2UIComponent]:
        """Build component tree from flat A2UI list.

        A2UI uses flat list with parent references. This builds
        the actual tree structure.
        """
        by_id: dict[str, A2UIComponent] = {c.id: c for c in payload.components}
        roots: list[A2UIComponent] = []

        for comp in payload.components:
            if comp.parent is None:
                roots.append(comp)
            elif comp.parent in by_id:
                parent = by_id[comp.parent]
                if comp.id not in parent.children:
                    parent.children.append(comp.id)

        return roots


def _map_to_native_type(a2ui_type: str) -> ComponentType:
    """Map A2UI type to native ComponentType."""
    spec = COMPONENT_CATALOG.get(a2ui_type)
    if spec:
        return spec.native_type
    return ComponentType.CUSTOM


def _convert_component(
    a2ui_comp: A2UIComponent,
    by_id: dict[str, A2UIComponent],
    children_map: dict[str, list[str]],
) -> UIComponent:
    """Convert A2UI component to native UIComponent."""
    native_type = _map_to_native_type(a2ui_comp.type)

    # Build props, preserving A2UI type for custom handling
    props = dict(a2ui_comp.props)
    props["_a2ui_type"] = a2ui_comp.type
    if a2ui_comp.data_model:
        props["_data_model"] = a2ui_comp.data_model

    # Recursively convert children
    children: list[UIComponent] = []
    child_ids = children_map.get(a2ui_comp.id, [])
    for child_id in child_ids:
        if child_id in by_id:
            children.append(_convert_component(by_id[child_id], by_id, children_map))

    return UIComponent(
        id=a2ui_comp.id,
        component_type=native_type,
        props=props,
        children=children,
    )


def a2ui_to_ui_view(
    payload: dict[str, Any],
    view_id: str | None = None,
    view_name: str = "A2UI View",
) -> UIView:
    """Convert A2UI payload to native UIView.

    Args:
        payload: Raw A2UI JSON payload from agent
        view_id: Optional view ID (generated if not provided)
        view_name: Name for the view

    Returns:
        UIView with converted components
    """
    parsed = A2UIParser.parse(payload)
    by_id: dict[str, A2UIComponent] = {c.id: c for c in parsed.components}

    # Build children map (parent_id -> list of child_ids)
    children_map: dict[str, list[str]] = {}
    roots: list[A2UIComponent] = []

    for comp in parsed.components:
        if comp.parent is None:
            roots.append(comp)
        else:
            if comp.parent not in children_map:
                children_map[comp.parent] = []
            children_map[comp.parent].append(comp.id)

    # Convert each root and its children
    components: list[UIComponent] = []
    for root in roots:
        components.append(_convert_component(root, by_id, children_map))

    return UIView(
        id=view_id or str(uuid.uuid4()),
        name=view_name,
        components=components,
        metadata={
            "a2ui_version": parsed.version,
            "source": "a2ui",
            **parsed.metadata,
        },
    )


def ui_view_to_a2ui(view: UIView) -> dict[str, Any]:
    """Convert native UIView back to A2UI format.

    Useful for round-tripping or agent inspection.
    """
    components: list[dict[str, Any]] = []

    def _flatten(comp: UIComponent, parent_id: str | None = None) -> None:
        props = {k: v for k, v in comp.props.items() if not k.startswith("_")}
        a2ui_type = comp.props.get("_a2ui_type", comp.component_type.value)

        a2ui_comp: dict[str, Any] = {
            "id": comp.id,
            "type": a2ui_type,
        }
        if props:
            a2ui_comp["props"] = props
        if parent_id:
            a2ui_comp["parent"] = parent_id
        if "_data_model" in comp.props:
            a2ui_comp["dataModel"] = comp.props["_data_model"]

        components.append(a2ui_comp)

        for child in comp.children:
            _flatten(child, comp.id)

    for root in view.components:
        _flatten(root)

    return {
        "components": components,
        "version": view.metadata.get("a2ui_version", "0.8"),
        "metadata": {
            k: v for k, v in view.metadata.items()
            if k not in ("a2ui_version", "source")
        },
    }
