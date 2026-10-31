"""Page skeleton renderer — standardized 3-zone brick view layout.

Zone 1: slim hero bar | Zone 2: metrics strip + controls | Zone 3: output.
Bricks declare what goes in each zone via data dicts.
This renderer handles the layout chrome; child components
are rendered by the standard HTMX renderers.

Layout uses CSS Grid "bento" pattern for a structured, modern feel.
"""

from __future__ import annotations

from typing import Callable

from ..models import ComponentType, UIComponent


def render_page_skeleton(
    c: UIComponent, render_child: Callable[[UIComponent], str],
) -> str:
    """Render the 3-zone page skeleton layout."""
    p = c.props
    title = p.get("title", "")
    subtitle = p.get("subtitle", "")
    icon = p.get("icon", "")
    gradient = p.get("gradient", "from-primary to-secondary")
    tooltip = p.get("tooltip", "")

    hero = _render_hero(c.id, icon, title, subtitle, gradient, tooltip)

    info_children = [ch for ch in c.children if ch.props.get("zone") == "info"]
    ctrl_children = [ch for ch in c.children if ch.props.get("zone") == "controls"]
    zone2 = _render_zone2(info_children, ctrl_children, render_child)

    output_children = [
        ch for ch in c.children
        if ch.props.get("zone") not in ("info", "controls")
    ]
    read_children = [
        ch for ch in output_children
        if ch.component_type != ComponentType.ACTION_PANE
    ]
    write_children = [
        ch for ch in output_children
        if ch.component_type == ComponentType.ACTION_PANE
    ]
    read_html = "".join(render_child(ch) for ch in read_children)
    write_html = "".join(render_child(ch) for ch in write_children)

    divider = ""
    if read_html and write_html:
        divider = (
            '<div class="divider text-base-content/40 text-xs'
            ' uppercase tracking-widest my-1">Actions</div>'
        )

    output_wrap = ""
    combined = f"{read_html}{divider}{write_html}"
    if combined:
        layout = p.get("output_layout", "")
        if layout == "two-column" and len(read_children) >= 2:
            # 2-column grid on wide screens for output children
            cols = "".join(
                f'<div class="min-w-0">{render_child(ch)}</div>'
                for ch in read_children
            )
            write_wrap = (
                f'{divider}{write_html}' if write_html else ""
            )
            output_wrap = (
                f'<div class="grid grid-cols-1 lg:grid-cols-2'
                f' gap-4 flex-1">{cols}</div>{write_wrap}'
            )
        else:
            output_wrap = (
                f'<div class="flex-1 flex flex-col gap-3">'
                f'{combined}</div>'
            )

    toast = _toast_container()
    css = _page_css()

    return (
        f'{css}'
        f'<div class="space-y-3 flex-1 flex flex-col" id="comp-{c.id}">'
        f'{hero}{zone2}{output_wrap}{toast}</div>'
    )


def _render_zone2(
    info_children: list, ctrl_children: list,
    render_child: Callable[[UIComponent], str],
) -> str:
    """Render zone 2: compact metric strip + controls as toolbar row."""
    if not info_children and not ctrl_children:
        return ""

    info_strip = ""
    if info_children:
        inner = "".join(render_child(ch) for ch in info_children)
        info_strip = (
            f'<div class="stats stats-horizontal shadow-sm'
            f' bg-base-100 w-full text-sm">{inner}</div>'
        )

    ctrl_html = "".join(render_child(ch) for ch in ctrl_children)
    ctrl_results = "".join(
        f'<div id="result-{ch.id}" class="mt-2"></div>'
        for ch in ctrl_children
        if ch.props.get("tool") or ch.props.get("action")
    )

    if info_children and ctrl_children:
        return (
            f'<div class="flex flex-col gap-3">'
            f'{info_strip}{ctrl_html}</div>'
            f'{ctrl_results}'
        )
    if info_children:
        return info_strip
    return f'<div>{ctrl_html}</div>{ctrl_results}'


def _render_hero(
    cid: str, icon: str, title: str, subtitle: str,
    gradient: str, tooltip: str = "",
) -> str:
    """Render a slim gradient hero bar — Slack-channel-header style."""
    icon_h = f'<span class="text-lg mr-2">{icon}</span>' if icon else ""
    sub_h = (
        f'<span class="text-primary-content/60 text-xs ml-3">'
        f'{subtitle}</span>'
    ) if subtitle else ""
    tip_h = ""
    if tooltip:
        from .heroicons import heroicon
        tip_icon = heroicon(
            "information-circle",
            "w-3.5 h-3.5 stroke-current text-primary-content/40 cursor-help",
        )
        tip_h = (
            f'<div class="tooltip tooltip-bottom ml-2"'
            f' data-tip="{tooltip}">{tip_icon}</div>'
        )
    return (
        f'<div class="bg-gradient-to-r {gradient} rounded-box px-4 py-2'
        f' text-primary-content shadow-sm">'
        f'<div class="flex items-center">{icon_h}'
        f'<h1 class="text-sm font-bold tracking-wide uppercase">{title}</h1>'
        f'{tip_h}{sub_h}</div></div>'
    )


def _toast_container() -> str:
    """Alpine.js toast that listens for custom 'toast' events from forms."""
    return (
        '<div x-data="{show:false,msg:\'\',type:\'success\'}"'
        ' @toast.window="msg=$event.detail.message;'
        'type=$event.detail.type||\'success\';show=true;'
        'setTimeout(()=>show=false,3000)"'
        ' class="toast toast-end toast-bottom z-50 fixed"'
        ' x-show="show" x-transition>'
        '<div class="alert shadow-lg"'
        ' :class="type===\'error\'?\'alert-error\':\'alert-success\'">'
        '<span x-text="msg"></span></div></div>'
    )


def _page_css() -> str:
    """Inject page-level CSS: animations, compact stats."""
    return (
        '<style>'
        '@keyframes fadeIn{from{opacity:0;transform:translateY(6px)}'
        'to{opacity:1;transform:translateY(0)}}'
        '.animate-fade-in{animation:fadeIn .3s ease-out both}'
        '@keyframes countUp{from{opacity:0;transform:translateY(4px)}'
        'to{opacity:1;transform:translateY(0)}}'
        '.animate-count{animation:countUp .4s ease-out both}'
        '.stats-horizontal .stat{padding:.5rem .75rem}'
        '.stats-horizontal .stat-value{font-size:.875rem}'
        '.stats-horizontal .stat-title{font-size:.65rem}'
        '.stats-horizontal .stat-figure svg{width:1.25rem;height:1.25rem}'
        '</style>'
    )
