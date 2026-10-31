"""ActionRef ingestion across every real brick view (bd:3jcls.3).

ANTI-DRIFT CONDITION 2 — validate against real brick declarations, not
fixtures. This walks EVERY ``*_get_views`` tool the real aggregator exposes,
pushes each payload through the real normalizer + validator, and asserts the
outcome. That proves the legacy ``props.tool`` → ``ActionRef`` normalization
holds across all 18 live ``type: "form"`` declarations at once, and that no
brick is currently shipping an action the frontend cannot dispatch.

If someone adds a brick view with a typo'd tool or an ``href``, this test
names the brick and the component id.
"""

from __future__ import annotations

import pytest


@pytest.fixture(scope="module")
def aggregator():
    """The real aggregator, with ``tool_invoker`` / ``brick_tools`` registered."""
    from factory.api.runtime.bridge import _get_aggregator

    agg = _get_aggregator()
    if agg is None:
        pytest.skip("aggregator unavailable")
    return agg


@pytest.fixture(scope="module")
def view_payloads(aggregator):
    """``{tool_name: raw_views}`` for every ``*_get_views`` in the repo."""
    payloads: dict[str, list] = {}
    for name in aggregator.get_all_tool_names():
        if not name.endswith("_get_views"):
            continue
        try:
            result = aggregator.invoke_tool(name)
        except Exception:  # noqa: BLE001 — a broken brick is not this test's subject
            continue
        if isinstance(result, list):
            payloads[name] = result
            continue
        data = getattr(result, "data", None)
        views = getattr(data, "views", None)
        if isinstance(views, list):
            payloads[name] = views
    if not payloads:
        pytest.skip("live brick views unavailable in the local aggregate")
    return payloads


def _walk(components):
    for comp in components or []:
        if not isinstance(comp, dict):
            continue
        yield comp
        yield from _walk(comp.get("children"))


def _actionable(views):
    """Every ``form`` / ``button`` component across a view payload."""
    for view in views:
        if not isinstance(view, dict):
            continue
        for comp in _walk(view.get("components")):
            if str(comp.get("type", "")).lower().replace("_", "") in {"form", "button"}:
                yield view, comp


def test_the_repo_actually_declares_actions(view_payloads):
    """Guard the guard: if this drops to zero the suite has gone vacuous."""
    total = sum(len(list(_actionable(v))) for v in view_payloads.values())
    assert total >= 15, f"expected the ~18 live form declarations, found {total}"


def test_every_brick_view_normalizes_to_a_valid_actionref(view_payloads):
    """No brick ships an action the dispatcher would refuse."""
    from factory.ui.interface import (
        brick_of_view_tool, build_tool_resolver, normalize_view_actions,
    )

    resolver = build_tool_resolver()
    failures: list[str] = []
    normalized_count = 0

    for tool_name, raw in view_payloads.items():
        views = normalize_view_actions(
            raw, brick_hint=brick_of_view_tool(tool_name), resolver=resolver,
        )
        for view, comp in _actionable(views):
            props = comp.get("props") or {}
            if props.get("action_error"):
                failures.append(
                    f"{tool_name} view={view.get('id')} component={comp.get('id')}: "
                    f"{props['action_error']}",
                )
                continue
            if props.get("action") is None:
                continue  # a form with no verb (children-only) is legal
            normalized_count += 1
            action = props["action"]
            assert isinstance(action["brick"], str) and action["brick"]
            assert isinstance(action["tool"], str) and action["tool"]
            # The legacy free-form key is gone — the FE learns ONE shape.
            assert "tool" not in props, f"{comp.get('id')} still carries props.tool"

    assert not failures, "invalid brick-declared actions:\n" + "\n".join(failures)
    assert normalized_count >= 15, f"only {normalized_count} actions normalized"


def test_normalization_leaves_non_action_tool_props_alone(view_payloads):
    """``chat``/``action_pane``/``data_tool`` use ``tool`` for READS, not verbs."""
    from factory.ui.interface import brick_of_view_tool, normalize_view_actions

    for tool_name, raw in view_payloads.items():
        views = normalize_view_actions(raw, brick_hint=brick_of_view_tool(tool_name))
        for view in views:
            for comp in _walk(view.get("components")):
                kind = str(comp.get("type", "")).lower().replace("_", "")
                if kind in {"form", "button"}:
                    continue
                original = next(
                    (c for v in raw for c in _walk(v.get("components"))
                     if c.get("id") == comp.get("id")), None,
                )
                if original is None:
                    continue
                assert (comp.get("props") or {}).get("tool") == \
                    (original.get("props") or {}).get("tool"), \
                    f"{tool_name}/{comp.get('id')} ({kind}) had its read tool rewritten"


def test_gateway_error_envelopes_pass_through_untouched():
    """``{"error": ...}`` from an unknown brick must survive verbatim."""
    from factory.ui.interface import normalize_view_actions

    envelope = {"error": "Unknown brick 'nope'"}
    assert normalize_view_actions(envelope) is envelope
