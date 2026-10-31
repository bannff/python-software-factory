"""Server-side ActionRef normalization for brick-declared views (bd:3jcls.3).

Runs at view INGESTION — every ``*_get_views`` payload on its way to the
frontend passes through :func:`normalize_view_actions`. Two jobs:

1. Rewrite the legacy free-form ``props["tool"]`` string that 18 bricks
   already emit on ``type: "form"`` components into a validated
   ``props["action"]`` :class:`~.actions.ActionRef` dict. The frontend then
   learns exactly ONE shape and carries zero back-compat branch.
2. Validate anything a brick declared as ``props["action"]`` directly, so a
   forbidden ``url`` key or a typo'd tool name fails here rather than at the
   user's click.

Scope is deliberately narrow: only ``form`` and ``button`` components. Other
component types use ``props["tool"]`` for READS (``chat`` → ``agent_reason``)
or nested legacy specs (``action_pane`` → ``props["actions"][].tool``, an
htmx-only surface that the shared renderer maps to a plain Card). Rewriting
those would break working paths for no gain.

Failure posture: a bad action does not blank the whole tab. The offending
component gets ``props["action_error"]`` (rendered as a visible error by
``useAction``) and the rest of the view survives. The error is also logged at
WARNING so a broken authoring change is not silent.
"""

from __future__ import annotations

import logging
from typing import Any

from .actions import ActionRefError, ToolResolver, parse_action_ref

logger = logging.getLogger(__name__)

#: Component types whose ``props.tool`` / ``props.action`` is a VERB.
_ACTIONABLE_TYPES = frozenset({"form", "button"})


def _norm_type(raw: Any) -> str:
    """Case+underscore-insensitive type key (mirrors the FE ``_norm``)."""
    return str(raw or "").lower().replace("_", "")


def brick_of_view_tool(tool_name: str) -> str | None:
    """Derive the owning brick from a ``<brick>_get_views`` tool name."""
    suffix = "_get_views"
    if not tool_name.endswith(suffix):
        return None
    return tool_name[: -len(suffix)] or None


def normalize_component_action(
    component: dict[str, Any],
    *,
    brick_hint: str | None,
    resolver: ToolResolver | None = None,
) -> dict[str, Any]:
    """Normalize one component dict in place-ish (returns a new dict).

    Non-actionable types and components with no action declaration are
    returned unchanged (same object) so the walker stays cheap.
    """
    if _norm_type(component.get("type")) not in _ACTIONABLE_TYPES:
        return component

    props = component.get("props")
    if not isinstance(props, dict):
        return component

    raw = props.get("action", props.get("tool"))
    if raw is None:
        return component

    new_props = dict(props)
    new_props.pop("tool", None)
    try:
        new_props["action"] = parse_action_ref(
            raw, brick_hint=brick_hint, resolver=resolver,
        ).to_dict()
        new_props.pop("action_error", None)
    except ActionRefError as exc:
        # Visible, not swallowed — the specific defect bd:372an fixed.
        new_props["action"] = None
        new_props["action_error"] = str(exc)
        logger.warning(
            "Invalid action on component %s (brick=%s): %s",
            component.get("id"), brick_hint, exc,
        )
    return {**component, "props": new_props}


def _walk(
    components: Any,
    *,
    brick_hint: str | None,
    resolver: ToolResolver | None,
) -> list[Any]:
    """Recursively normalize a component list, preserving order and shape."""
    if not isinstance(components, list):
        return components
    out: list[Any] = []
    for comp in components:
        if not isinstance(comp, dict):
            out.append(comp)
            continue
        normalized = normalize_component_action(
            comp, brick_hint=brick_hint, resolver=resolver,
        )
        children = normalized.get("children")
        if isinstance(children, list):
            walked = _walk(children, brick_hint=brick_hint, resolver=resolver)
            if walked is not children:
                normalized = {**normalized, "children": walked}
        out.append(normalized)
    return out


def normalize_view_actions(
    views: Any,
    *,
    brick_hint: str | None = None,
    resolver: ToolResolver | None = None,
) -> Any:
    """Normalize every action declaration in a ``*_get_views`` payload.

    Args:
        views: The raw list of view dicts. Non-list input is passed through
            untouched (the aggregator returns ``{"error": ...}`` envelopes
            for unknown bricks and those must survive verbatim).
        brick_hint: Owning brick, used when an action omits ``brick``.
            Falls back to each view's own ``brick`` field.
        resolver: Optional tool-existence probe — see
            :func:`~.actions.parse_action_ref`.

    Returns:
        A payload of the same shape with every actionable component's
        ``props["action"]`` replaced by a validated ``ActionRef`` dict.
    """
    if not isinstance(views, list):
        return views
    out: list[Any] = []
    for view in views:
        if not isinstance(view, dict):
            out.append(view)
            continue
        hint = view.get("brick") or brick_hint
        components = _walk(
            view.get("components"), brick_hint=hint, resolver=resolver,
        )
        out.append(
            view if components is view.get("components")
            else {**view, "components": components}
        )
    return out
