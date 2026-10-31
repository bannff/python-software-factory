"""HTMX component renderers with polished DaisyUI styling.

Semantic hints from component props:
- intent: "hero"|"critical"|"success"|"warning"|"muted"
- collapsible: true — DaisyUI collapse wrapper
- loading: true — skeleton placeholder instead of content
- icon: "chart"|"list"|"document"|"users" — stat-figure SVG

Renderers are the Single Source of Beauty.
"""

from typing import Any
from ..models import UIComponent
from .htmx_intent import intent_cls, hero_gradient_cls, maybe_collapse
from .htmx_intent import METRIC_VALUE_CLS, METRIC_FIGURE_CLS
from .htmx_icons import ALERT_SVG, SKELETON, stat_icon
from .htmx_form_fields import render_field, metric_tooltip
from .htmx_sparkline import render_sparkline as _render_sparkline


def _skel(variant: str, c: UIComponent) -> str:
    return SKELETON.get(variant, SKELETON["text"]).format(cid=c.id)


def render_text(c: UIComponent) -> str:
    if c.props.get("loading"):
        return _skel("text", c)
    variant = c.props.get("variant", "body")
    # Catalog canonical 'text'; 'content'/'value' aliased (mirrors renderers-basic.tsx).
    content = c.props.get("text") or c.props.get("content") or c.props.get("value") or ""
    hero = hero_gradient_cls(c)
    if hero:
        return f'<div class="{hero}" id="comp-{c.id}"><h1 class="text-5xl font-bold">{content}</h1></div>'
    cls_map = {"h1": "text-4xl font-extrabold tracking-tight", "h2": "text-3xl font-bold tracking-tight",
               "h3": "text-2xl font-semibold", "body": "text-base leading-relaxed",
               "caption": "text-sm text-base-content/60 italic"}
    css = f'{cls_map.get(variant, "text-base")} {intent_cls(c)}'.strip()
    tag = {"h1": "h1", "h2": "h2"}.get(variant, "p")
    # A2UI catalog optionalProps: color→CSS color, size→font-size
    # (number/numeric-string → px), align→text-align. Catalog-declared
    # semantic props only — no free-form style pass-through.
    parts = []
    if c.props.get("color"):
        parts.append(f"color: {c.props['color']}")
    size = c.props.get("size")
    if isinstance(size, (int, float)):
        parts.append(f"font-size: {size}px")
    elif isinstance(size, str) and size.isdigit():
        parts.append(f"font-size: {size}px")
    elif isinstance(size, str) and size:
        parts.append(f"font-size: {size}")
    align = c.props.get("align")
    if align:
        parts.append(f"text-align: {align}")
    style = f' style="{"; ".join(parts)}"' if parts else ""
    return f'<{tag} class="{css}"{style} id="comp-{c.id}">{content}</{tag}>'


def render_button(c: UIComponent) -> str:
    label, variant = c.props.get("label", "Button"), c.props.get("variant", "primary")
    action = c.props.get("hx_action", "")
    hx = f'hx-post="{action}" hx-swap="outerHTML"' if action else ""
    return (f'<button class="btn btn-{variant} shadow-md hover:shadow-lg transition-all'
            f' {intent_cls(c)}" id="comp-{c.id}" {hx}>{label}</button>')


def render_card(c: UIComponent, render_fn) -> str:
    if c.props.get("loading"):
        return _skel("card", c)
    title, content = c.props.get("title", ""), c.props.get("content", "")
    children = "\n".join(render_fn(ch) for ch in c.children)
    badge = c.props.get("badge", "")
    badge_h = f' <div class="badge badge-secondary">{badge}</div>' if badge else ""
    glass = c.props.get("glass", False)
    card_cls = "glass-card rounded-xl" if glass else "card bg-base-100 shadow-xl"
    inner = (f'<div class="{card_cls} hover:shadow-2xl transition-shadow'
             f' {intent_cls(c)}" id="comp-{c.id}"><div class="card-body">'
             f'<h3 class="card-title">{title}{badge_h}</h3>'
             f'<p class="text-base-content/80">{content}</p>{children}</div></div>')
    return maybe_collapse(c, inner, title)


def render_metric(c: UIComponent) -> str:
    if c.props.get("loading"):
        return _skel("metric", c)
    label, value = c.props.get("label", ""), c.props.get("value", "")
    trend, intent = c.props.get("trend", ""), c.props.get("intent", "")
    tooltip = c.props.get("tooltip", "")
    icon_key = c.props.get("icon", "default")
    data_tool = c.props.get("data_tool", "")
    spark_data = c.props.get("sparkline", [])
    fig_cls = METRIC_FIGURE_CLS.get(intent, "text-primary")
    svg = stat_icon(icon_key)
    fig = f'<div class="stat-figure {fig_cls}">{svg}</div>'
    val_cls = f'stat-value {METRIC_VALUE_CLS.get(intent, "")}'.strip()
    t_cls = {"up": "text-success", "down": "text-error"}.get(trend, "")
    t_icon = {"up": "↗︎", "down": "↘︎"}.get(trend, "")
    t_val = c.props.get("trend_value", "")
    desc = f'<div class="stat-desc {t_cls}">{t_icon} {t_val}</div>' if t_val else ""
    tip_h = metric_tooltip(tooltip) if tooltip else ""
    spark_h = _render_sparkline(spark_data, intent) if spark_data else ""
    metric_key = c.props.get("metric_key", "")
    mk_qs = f"?key={metric_key}" if metric_key else ""
    hx = (f' hx-get="/api/metrics/{data_tool}{mk_qs}" hx-trigger="load"'
          f' hx-target="find .stat-value" hx-swap="innerHTML"'
          if data_tool else "")
    return (f'<div class="stat" x-data x-intersect.once="$el.classList.add(\'animate-fade-in\')"'
            f'{hx} id="comp-{c.id}">{fig}'
            f'<div class="stat-title flex items-center gap-1">{label}{tip_h}</div>'
            f'<div class="{val_cls}">{value}{spark_h}</div>{desc}</div>')


def render_alert(c: UIComponent) -> str:
    msg, sev = c.props.get("message", ""), c.props.get("severity", "info")
    icon = ALERT_SVG.get(sev, ALERT_SVG["info"])
    lnk = c.props.get("link")
    lnk_h = f' <a href="{lnk["href"]}" class="link link-hover">{lnk["label"]}</a>' if lnk else ""
    return f'<div class="alert alert-{sev} shadow-sm" id="comp-{c.id}">{icon}<span>{msg}{lnk_h}</span></div>'


def render_progress(c: UIComponent) -> str:
    value, label = c.props.get("value", 0), c.props.get("label", "")
    variant, intent = c.props.get("variant", "linear"), c.props.get("intent", "")
    _c = {"critical": "error", "success": "success", "warning": "warning"}
    if variant == "circular":
        color = f"text-{_c.get(intent, 'primary')}"
        return (f'<div class="flex flex-col items-center gap-1" id="comp-{c.id}">'
                f'<div class="radial-progress {color}" style="--value:{value}; --size:4rem;"'
                f' role="progressbar">{value}%</div><span class="text-sm">{label}</span></div>')
    color = f"progress-{_c.get(intent, 'primary')}"
    return (f'<div class="space-y-1" id="comp-{c.id}">'
            f'<div class="flex justify-between text-sm"><span>{label}</span>'
            f'<span class="text-base-content/60">{value}%</span></div>'
            f'<progress class="progress {color} w-full" value="{value}" max="100"></progress></div>')


def render_form(c: UIComponent) -> str:
    fields, tool = c.props.get("fields", []), c.props.get("tool", "")
    action = c.props.get("action", "") or (f"/api/tools/{tool}" if tool else "")
    submit = c.props.get("submit_label", "Submit")
    desc = c.props.get("description", "")
    title = c.props.get("title", "")
    target_id = f"result-{c.id}"
    hx = (f'hx-post="{action}" hx-target="#{target_id}" hx-swap="innerHTML"'
          f' hx-indicator="#{target_id}-spinner"'
          f' @htmx:after-request.window="if($event.detail.target.id===\'{target_id}\')'
          f'{{$event.detail.successful'
          f'?$dispatch(\'toast\',{{message:\'Done\',type:\'success\'}})'
          f':$dispatch(\'toast\',{{message:\'Request failed\',type:\'error\'}})}}"'
          if action else "")
    fh = "\n".join(render_field(f) for f in fields)
    spinner = f'<span id="{target_id}-spinner" class="htmx-indicator loading loading-spinner loading-sm"></span>'
    title_h = (f'<h3 class="text-sm font-semibold text-base-content/70'
               f' uppercase tracking-wide mb-2">{title}</h3>') if title else ""
    desc_h = f'<p class="text-sm text-base-content/60 mb-2">{desc}</p>' if desc else ""
    inline_result = "" if c.props.get("zone") == "controls" else f'<div id="{target_id}" class="mt-4"></div>'
    return (f'<div class="card bg-base-100 shadow-sm {intent_cls(c)}" id="comp-{c.id}">'
            f'<div class="card-body p-4">{title_h}{desc_h}<form class="space-y-3" {hx}>{fh}'
            f'<div class="pt-1"><button type="submit" class="btn btn-primary btn-sm'
            f' shadow-md hover:shadow-lg transition-all gap-2"'
            f' hx-disabled-elt="this">'
            f'{spinner}{submit}</button></div></form>'
            f'{inline_result}</div></div>')


def render_list(c: UIComponent) -> str:
    items = c.props.get("items", [])
    ih = "".join(f'<li class="py-1 border-b border-base-200 last:border-0">{i}</li>' for i in items)
    return f'<ul class="menu bg-base-100 rounded-box {intent_cls(c)}" id="comp-{c.id}">{ih}</ul>'


def render_chart(c: UIComponent) -> str:
    ct, title = c.props.get("chart_type", "line"), c.props.get("title", "")
    return (f'<div class="card bg-base-100 shadow-sm" id="comp-{c.id}"><div class="card-body">'
            f'<h3 class="card-title text-sm">{title}</h3>'
            f'<div class="h-48 flex items-center justify-center bg-base-200/50 rounded-lg'
            f' border border-dashed border-base-300">'
            f'<span class="text-base-content/40">[{ct.upper()} CHART]</span></div></div></div>')


def render_image(c: UIComponent) -> str:
    src, alt = c.props.get("src", ""), c.props.get("alt", "")
    return (f'<figure class="rounded-xl overflow-hidden shadow-sm" id="comp-{c.id}">'
            f'<img src="{src}" alt="{alt}" class="w-full" /></figure>')


def render_custom(c: UIComponent) -> str:
    return (f'<div class="p-4 bg-base-200 rounded-lg border border-dashed border-base-300"'
            f' id="comp-{c.id}">[Custom: {c.component_type.value}]</div>')

def _rich_empty(c: UIComponent) -> str | None:
    """Render a rich empty state from the empty_state prop, or None."""
    es = c.props.get("empty_state")
    if not es:
        return None
    from .heroicons import heroicon
    msg = es.get("message", "No data yet")
    hint = es.get("hint", "")
    icon = heroicon(es.get("icon", "inbox"), "w-12 h-12 stroke-current text-base-content/20")
    hint_h = f'<p class="text-xs text-base-content/40 mt-1">{hint}</p>' if hint else ""
    return (f'<div class="card bg-base-100 shadow-sm flex-1 {intent_cls(c)}" id="comp-{c.id}">'
            f'<div class="flex flex-col items-center justify-center py-12 gap-2">'
            f'{icon}<p class="text-sm text-base-content/50">{msg}</p>'
            f'{hint_h}</div></div>')


def _card_empty(msg: str, c: UIComponent) -> str:
    return (f'<div class="card bg-base-100 shadow-sm flex-1 {intent_cls(c)}" id="comp-{c.id}">'
            f'<div class="text-center py-8 text-base-content/50">{msg}</div></div>')


def layout_to_class(layout: dict[str, Any]) -> str:
    if layout.get("type") == "grid":
        return f"grid grid-cols-{layout.get('columns', 1)} gap-4"
    if layout.get("type") == "flex":
        return f"flex flex-{layout.get('direction', 'row')} gap-4"
    return "space-y-4"
