"""HTMX renderers for extended component types.

Covers: hero, tabs, breadcrumbs, modal, toast.
Split from htmx_renderers.py to stay under 200 LOC per file.
"""

from ..models import UIComponent
from .htmx_icons import ALERT_SVG


def render_hero(c: UIComponent) -> str:
    title = c.props.get("title", "")
    subtitle = c.props.get("subtitle", "")
    cta_text = c.props.get("cta_text", "")
    cta_href = c.props.get("cta_href", "#")
    image = c.props.get("image", "")
    overlay = c.props.get("overlay", False)
    style = f' style="background-image: url({image});"' if image else ""
    overlay_h = '<div class="hero-overlay bg-opacity-60 rounded-box"></div>' if image and overlay else ""
    text_cls = "text-neutral-content" if image else ""
    cta_h = f'<a href="{cta_href}" class="btn btn-primary">{cta_text}</a>' if cta_text else ""
    sub_h = f'<p class="py-6">{subtitle}</p>' if subtitle else ""
    return (
        f'<div class="hero min-h-[40vh] bg-base-200 rounded-box"{style}'
        f' id="comp-{c.id}">{overlay_h}'
        f'<div class="hero-content text-center {text_cls}"><div class="max-w-md">'
        f'<h1 class="text-5xl font-bold">{title}</h1>{sub_h}{cta_h}'
        f'</div></div></div>'
    )


def render_tabs(c: UIComponent) -> str:
    tabs = c.props.get("tabs", [])
    active = c.props.get("active", tabs[0]["id"] if tabs else "")
    tab_btns = ""
    tab_panels = ""
    for t in tabs:
        tid = t.get("id", "")
        label = t.get("label", "")
        content = t.get("content", "")
        if not content and t.get("lazy_tool"):
            tool = t["lazy_tool"]
            hint = t.get("empty_hint", "")
            hint_h = (
                f'<p class="text-xs text-base-content/40 mt-1">'
                f'{hint}</p>'
            ) if hint else ""
            content = (
                f'<div hx-get="/api/tools/{tool}" hx-trigger="load"'
                f' hx-swap="innerHTML">'
                f'<span class="loading loading-spinner"></span>'
                f'{hint_h}</div>'
            )
        tab_btns += (
            f'<a class="tab tab-sm" :class="active === \'{tid}\''
            f' && \'tab-active !text-primary font-semibold\'"'
            f' @click="active = \'{tid}\'">{label}</a>'
        )
        tab_panels += (
            f'<div x-show="active === \'{tid}\'"'
            f' x-transition:enter="transition ease-out duration-200"'
            f' x-transition:enter-start="opacity-0 translate-y-1"'
            f' x-transition:enter-end="opacity-100 translate-y-0"'
            f' class="p-4">{content}</div>'
        )
    return (
        f'<div x-data="{{active: \'{active}\'}}" id="comp-{c.id}"'
        f' class="flex-1 flex flex-col glass-card rounded-xl">'
        f'<div class="tabs tabs-bordered px-4 pt-3">{tab_btns}</div>'
        f'<div class="flex-1">{tab_panels}</div></div>'
    )


def render_breadcrumbs(c: UIComponent) -> str:
    items = c.props.get("items", [])
    crumbs = "".join(
        f'<li><a href="{it.get("href", "#")}">{it.get("label", "")}</a></li>'
        for it in items
    )
    return f'<div class="breadcrumbs text-sm" id="comp-{c.id}"><ul>{crumbs}</ul></div>'


def render_modal(c: UIComponent) -> str:
    title = c.props.get("title", "")
    content = c.props.get("content", "")
    trigger = c.props.get("trigger_label", "Open")
    modal_id = f"modal-{c.id}"
    return (
        f'<div id="comp-{c.id}">'
        f'<button class="btn btn-primary" onclick="{modal_id}.showModal()">'
        f'{trigger}</button>'
        f'<dialog id="{modal_id}" class="modal">'
        f'<div class="modal-box"><h3 class="font-bold text-lg">{title}</h3>'
        f'<p class="py-4">{content}</p>'
        f'<div class="modal-action"><form method="dialog">'
        f'<button class="btn">Close</button></form></div></div>'
        f'<form method="dialog" class="modal-backdrop"><button>close</button>'
        f'</form></dialog></div>'
    )


def render_toast(c: UIComponent) -> str:
    msg = c.props.get("message", "")
    ttype = c.props.get("type", "info")
    duration = c.props.get("duration", 5000)
    dismissible = c.props.get("dismissible", True)
    icon = ALERT_SVG.get(ttype, ALERT_SVG["info"])
    dismiss_btn = (
        '<button class="btn btn-sm btn-ghost" @click="show = false">✕</button>'
        if dismissible else ""
    )
    return (
        f'<div x-data="{{show: true}}"'
        f' x-init="setTimeout(() => show = false, {duration})"'
        f' x-show="show"'
        f' x-transition:enter="transition ease-out duration-300"'
        f' x-transition:enter-start="opacity-0 translate-x-full"'
        f' x-transition:enter-end="opacity-100 translate-x-0"'
        f' x-transition:leave="transition ease-in duration-200"'
        f' x-transition:leave-start="opacity-100 translate-x-0"'
        f' x-transition:leave-end="opacity-0 translate-x-full"'
        f' class="toast toast-end toast-top z-50" id="comp-{c.id}">'
        f'<div class="alert alert-{ttype} shadow-lg">'
        f'{icon}<span>{msg}</span>{dismiss_btn}</div></div>'
    )
