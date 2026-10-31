"""Form field renderers for HTMX adapter.

Supports: text, number, select, textarea, range.
Each field can have an optional tooltip via the 'tooltip' prop.
Extracted from htmx_renderers.py to stay under 200 LOC.
"""


def render_field(f: dict) -> str:
    """Render a single form field — supports input, select, textarea, range."""
    name = f.get("name", "")
    label = f.get("label", name)
    ftype = f.get("type", "text")
    ph = f.get("placeholder", "")
    tip = f.get("tooltip", "")
    desc = f.get("description", "")
    tip_h = _tooltip(tip) if tip else ""
    desc_h = (f'<span class="label-text-alt text-base-content/50">'
              f'{desc}</span>') if desc else ""
    lbl = (f'<label class="label"><span class="label-text font-medium">'
           f'{label}</span>{tip_h}</label>')
    if ftype == "select":
        opts = "".join(
            f'<option value="{o.get("value","")}">{o.get("label","")}</option>'
            for o in f.get("options", []))
        return (f'<div class="form-control">{lbl}'
                f'<select name="{name}" class="select select-bordered'
                f' focus:select-primary">{opts}</select>{desc_h}</div>')
    if ftype == "textarea":
        return (f'<div class="form-control">{lbl}'
                f'<textarea name="{name}" class="textarea textarea-bordered'
                f' focus:textarea-primary h-24" placeholder="{ph}">'
                f'</textarea>{desc_h}</div>')
    if ftype == "range":
        mn, mx = f.get("min", 1), f.get("max", 10)
        val = f.get("value", mn)
        return (f'<div class="form-control" x-data="{{val: {val}}}">{lbl}'
                f'<input type="range" name="{name}" min="{mn}" max="{mx}"'
                f' value="{val}" class="range range-primary range-sm"'
                f' step="1" x-model="val" />'
                f'<div class="flex justify-between text-xs px-1">'
                f'<span>{mn}</span>'
                f'<span class="badge badge-sm badge-ghost" x-text="val"></span>'
                f'<span>{mx}</span></div>{desc_h}</div>')
    return (f'<div class="form-control">{lbl}'
            f'<input type="{ftype}" name="{name}"'
            f' class="input input-bordered focus:input-primary'
            f' transition-colors" placeholder="{ph}" />{desc_h}</div>')


def _tooltip(text: str) -> str:
    from .heroicons import heroicon
    icon = heroicon("information-circle", "w-4 h-4 stroke-current"
                    " text-base-content/40 cursor-help ml-1")
    return f'<div class="tooltip tooltip-left" data-tip="{text}">{icon}</div>'


def metric_tooltip(text: str) -> str:
    """Render a small info tooltip for metric stat titles."""
    from .heroicons import heroicon
    icon = heroicon("information-circle", "w-3.5 h-3.5 stroke-current"
                    " text-base-content/40 cursor-help")
    return f'<div class="tooltip tooltip-bottom" data-tip="{text}">{icon}</div>'
