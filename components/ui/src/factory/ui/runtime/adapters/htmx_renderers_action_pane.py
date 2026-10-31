"""HTMX renderer for the ACTION_PANE component type.

Renders a dropdown selector + dynamic form area that swaps via Alpine.js.
Replaces the tab-per-operation pattern with a single polymorphic pane:
one dropdown, one dynamic form, one Run button, one result area.

Props:
    actions: list of action dicts, each with:
        - id: unique action identifier
        - label: human-readable label for the dropdown
        - icon: optional emoji/icon prefix
        - tool: MCP tool name to call
        - submit_label: button text (default "Run")
        - fields: list of form field dicts (same schema as form component)
    default_action: id of the initially selected action (optional)
"""

from __future__ import annotations

from ..models import UIComponent
from .htmx_form_fields import render_field


def render_action_pane(c: UIComponent) -> str:
    """Render a polymorphic action pane with dropdown + dynamic form."""
    actions = c.props.get("actions", [])
    if not actions:
        return f'<div id="comp-{c.id}"></div>'

    default = c.props.get("default_action", actions[0]["id"])
    pane_id = f"action-pane-{c.id}"
    result_id = f"result-{c.id}"

    # Build dropdown options
    options = "".join(
        f'<option value="{a["id"]}"'
        f'{" selected" if a["id"] == default else ""}>'
        f'{a.get("icon", "")} {a["label"]}</option>'
        for a in actions
    )

    # Build one form per action, toggled by Alpine x-show
    forms = "".join(_render_action_form(a, result_id) for a in actions)

    action_label = c.props.get("action_label", "Action")

    return (
        f'<div class="card bg-base-100 shadow-sm" id="comp-{c.id}"'
        f' x-data="{{action: \'{default}\'}}">'
        f'<div class="card-body space-y-4">'
        # Dropdown selector
        f'<div class="form-control">'
        f'<label class="label">'
        f'<span class="label-text font-semibold">{action_label}</span></label>'
        f'<select class="select select-bordered select-primary'
        f' font-medium" x-model="action">{options}</select></div>'
        # Dynamic form area
        f'<div>{forms}</div>'
        # Shared result area
        f'<div id="{result_id}" class="mt-2"></div>'
        f'</div></div>'
    )


def _render_action_form(action: dict, result_id: str) -> str:
    """Render a single action's form, hidden by default via Alpine."""
    aid = action["id"]
    tool = action.get("tool", "")
    submit = action.get("submit_label", "Run")
    fields = action.get("fields", [])
    url = f"/api/tools/{tool}" if tool else ""

    hx = (
        f'hx-post="{url}" hx-target="#{result_id}" hx-swap="innerHTML"'
        f' hx-indicator="#{result_id}-spin"'
    ) if url else ""

    main = [f for f in fields if not f.get("group")]
    grouped = [f for f in fields if f.get("group")]
    main_html = "\n".join(render_field(f) for f in main)
    grouped_html = ""
    if grouped:
        inner = "\n".join(render_field(f) for f in grouped)
        grouped_html = (
            f'<div class="collapse collapse-arrow bg-base-200 rounded-box">'
            f'<input type="checkbox" />'
            f'<div class="collapse-title text-sm font-medium">Advanced</div>'
            f'<div class="collapse-content space-y-3">{inner}</div></div>'
        )
    spinner = (
        f'<span id="{result_id}-spin" class="htmx-indicator loading'
        f' loading-spinner loading-sm"></span>'
    )

    return (
        f'<div x-show="action === \'{aid}\'"'
        f' x-transition:enter="transition ease-out duration-150"'
        f' x-transition:enter-start="opacity-0 -translate-y-1"'
        f' x-transition:enter-end="opacity-100 translate-y-0">'
        f'<form class="space-y-3" {hx}>{main_html}{grouped_html}'
        f'<button type="submit" class="btn btn-primary btn-sm'
        f' shadow-md hover:shadow-lg transition-all gap-2">'
        f'{spinner}{submit}</button></form></div>'
    )
