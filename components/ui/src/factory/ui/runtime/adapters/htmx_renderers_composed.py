"""Composed page renderer — arranges panels in grid/stack/tabs layout.

Panels are pre-resolved UIComponents passed as children.
This renderer handles layout chrome only.
"""

from __future__ import annotations

from typing import Callable

from ..models import UIComponent


def render_composed_page(
    c: UIComponent, render_child: Callable[[UIComponent], str],
) -> str:
    """Render a composed_page component with its panel children."""
    p = c.props
    layout = p.get("layout", "grid")
    missing = p.get("missing_panels", [])

    parts: list[str] = []

    hero = p.get("hero")
    if hero:
        parts.append(_render_hero(hero))

    panel_htmls: list[tuple[str, str]] = []
    for child in c.children:
        size = (child.props.get("panel", {}).get("size_hint")
                or child.styles.get("size_hint", "half"))
        html = render_child(child)
        panel_htmls.append((size, html))

    for pid in missing:
        panel_htmls.append(("half", _missing_panel(pid)))

    if layout == "tabs":
        parts.append(_tabs_layout(c.children, panel_htmls))
    elif layout == "stack":
        parts.append(_stack_layout(panel_htmls))
    else:
        parts.append(_grid_layout(panel_htmls))

    return (
        f'<div class="space-y-4" id="comp-{c.id}">'
        + "\n".join(parts)
        + "</div>"
    )


def _grid_layout(panels: list[tuple[str, str]]) -> str:
    """CSS grid layout respecting size hints."""
    size_to_col = {
        "full": "col-span-full",
        "half": "lg:col-span-1",
        "third": "lg:col-span-1",
        "compact": "lg:col-span-1",
    }
    items = []
    for size, html in panels:
        col_cls = size_to_col.get(size, "lg:col-span-1")
        items.append(f'<div class="{col_cls} min-w-0">{html}</div>')
    return (
        '<div class="grid grid-cols-1 lg:grid-cols-2 gap-4">'
        + "\n".join(items)
        + "</div>"
    )


def _stack_layout(panels: list[tuple[str, str]]) -> str:
    """Vertical full-width stack."""
    items = [f"<div>{html}</div>" for _, html in panels]
    return (
        '<div class="flex flex-col gap-4">'
        + "\n".join(items)
        + "</div>"
    )


def _tabs_layout(
    children: list[UIComponent], panels: list[tuple[str, str]],
) -> str:
    """Tabbed layout — one panel per tab."""
    if not panels:
        return ""
    tab_buttons: list[str] = []
    tab_panels: list[str] = []
    group_id = id(children)
    for i, (child, (_, html)) in enumerate(zip(children, panels)):
        name = child.props.get("title", child.id)
        checked = ' checked="checked"' if i == 0 else ""
        tab_buttons.append(
            f'<input type="radio" name="composed-tabs-{group_id}"'
            f' role="tab" class="tab"{checked}'
            f' aria-label="{name}" />'
        )
        tab_panels.append(
            f'<div role="tabpanel" class="tab-content p-4">{html}</div>'
        )
    tabs = "".join(a + b for a, b in zip(tab_buttons, tab_panels))
    return f'<div role="tablist" class="tabs tabs-bordered">{tabs}</div>'


def _render_hero(hero: dict) -> str:
    """Render a hero section with title, subtitle, gradient, and CTAs."""
    title = hero.get("title", "")
    subtitle = hero.get("subtitle", "")
    icon = hero.get("icon", "")
    gradient = hero.get("gradient", "from-primary to-secondary")
    ctas = hero.get("cta", [])

    icon_h = f'<div class="text-4xl mb-2">{icon}</div>' if icon else ""
    sub_h = (
        f'<p class="text-lg opacity-80 mb-4">{subtitle}</p>'
        if subtitle else ""
    )
    cta_html = " ".join(
        f'<a href="{c["href"]}"'
        f' class="btn btn-sm bg-white/20 hover:bg-white/30'
        f' border-white/30 text-primary-content">{c["label"]}</a>'
        for c in ctas
    )
    cta_wrap = (
        f'<div class="flex gap-3 justify-center">{cta_html}</div>'
        if cta_html else ""
    )
    return (
        f'<div class="bg-gradient-to-r {gradient} rounded-box'
        f' p-8 text-primary-content text-center shadow-sm">'
        f"{icon_h}"
        f'<h1 class="text-2xl font-bold mb-1">{title}</h1>'
        f"{sub_h}{cta_wrap}</div>"
    )


def _missing_panel(panel_id: str) -> str:
    """Placeholder for a panel that wasn't found."""
    return (
        f'<div class="border-2 border-dashed border-base-300'
        f' rounded-box p-8 text-center text-base-content/40">'
        f'<p class="text-sm">Panel not found:'
        f" <code>{panel_id}</code></p></div>"
    )
