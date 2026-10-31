"""A2UI ``props.children`` lift helper for ``ui_paint_canvas``.

Carved out of ``paint_canvas.py`` to keep that module under the 200 LOC
tenet. Used at the producer boundary to normalize the agent's intuitive
``props.children`` shape into A2UI's canonical flat-siblings-with-
``parent:``-refs form before wire emit.

bd:python-factory-3hkqx round 3 — meta-architect verdict
``cec79d55-7ff3-41c0-b583-781bc5d7d2b7`` Q4. The FE consumer
(``a2ui-tree.ts``) handles all three child-shape variants defensively,
but normalizing at the producer keeps the wire contract canonical so
cross-snapshot/replay invariants and snapshot tests have a stable
shape to assert against.

SDK gap: A2UI is our own schema; no SDK ships normalization for it.
"""

from __future__ import annotations

from typing import Any


def lift_props_children(components: list[Any]) -> list[dict[str, Any]]:
    """Lift nested ``props.children: [...]`` into flat siblings with ``parent:`` refs.

    Agent's intuitive A2UI shape often nests children inside ``props.children``
    (e.g. ``Card{props:{title:"Hello", children:[Text{...}]}}``). The canonical
    A2UI schema (``a2ui/schema.py``) is flat siblings with ``parent: "<id>"``
    references. We normalize at the producer so the wire stays canonical
    and the FE consumer has a single shape to handle.

    Recursive — a Card with a Text child that itself has nested children
    is fully lifted. Components without nested children pass through.
    Empty/non-list ``children`` and non-dict items are no-ops.
    """
    out: list[dict[str, Any]] = []

    def _walk(comp: Any, parent_id: str | None) -> None:
        if not isinstance(comp, dict):
            return
        comp_id = comp.get("id")
        props = comp.get("props")
        nested: list[Any] = []
        clean_props = props
        if isinstance(props, dict):
            kids = props.get("children")
            if isinstance(kids, list) and kids:
                nested = kids
                clean_props = {k: v for k, v in props.items() if k != "children"}
        new_comp: dict[str, Any] = {**comp}
        if clean_props is not None:
            new_comp["props"] = clean_props
        if parent_id and "parent" not in new_comp:
            new_comp["parent"] = parent_id
        out.append(new_comp)
        if isinstance(comp_id, str):
            for child in nested:
                _walk(child, comp_id)

    for c in components:
        _walk(c, None)
    return out


__all__ = ["lift_props_children"]
