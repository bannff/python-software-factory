/**
 * Renderer style + className pass-through canary
 * (bd:python-factory-3hkqx round 6 — decorative-prop drop).
 *
 * The qa-tester verdict on round 5 (memory `ff4aba89` / round-5 +
 * round-6 prop-alias chain) found a NEW prop-drop class: the agent
 * emits decorative styling on Cards/Text/Alert via ``props.style``
 * (CSS-in-JS) and/or extra ``props.className`` (Tailwind utility
 * strings such as ``bg-gradient-to-b from-purple-900``) and the
 * renderer either ignores them entirely or only honors one side.
 *
 * Symptom: agent paints "Synthwave Arcade" with gradient sky, neon
 * sun, glowing skyline, alerts — but the live canvas shows a stack
 * of EMPTY white Cards. The text is in chat as the planned
 * description; the visuals never reach the DOM.
 *
 * Truth table built from
 * ``frontends/next-dashboard/components/renderer/renderers-*.tsx``
 * (read-only audit, no source changes in this consult round):
 *
 *   Renderer            | className | inline style | both
 *   --------------------|-----------|--------------|-----
 *   Text (Typography)   | YES       | NO           | NO
 *   Button              | YES       | NO           | NO
 *   Card                | YES       | NO           | NO    ← top of bug
 *   Alert               | YES       | NO           | NO    ← arcade alert
 *   Progress            | YES       | NO           | NO
 *   List                | YES       | NO           | NO
 *   Form                | YES       | NO           | NO
 *   Tabs                | YES       | NO           | NO
 *   Breadcrumb          | YES       | NO           | NO
 *   Dialog              | YES       | NO           | NO
 *   Toast               | NO        | NO           | NO
 *   Page                | YES       | NO           | NO    ← gradient hero only via own `gradient` prop
 *   Tree                | YES       | NO           | NO
 *   Custom              | YES       | NO           | NO
 *   Spacer              | NO (height/width only) | partial (own height/width) | NO
 *   Divider             | YES       | NO           | NO
 *   Table               | YES       | NO           | NO
 *   Chart               | YES       | NO           | NO
 *   Image               | YES       | NO           | NO
 *   Code                | YES       | NO           | NO
 *   Timeline            | YES       | NO           | NO
 *   Metric (MetricCard) | YES       | NO           | NO
 *   GraphViewer         | NO        | NO           | NO
 *   ItemList            | NO        | NO           | NO
 *   StatusDot           | NO        | NO           | NO
 *   TrendBadge          | NO        | NO           | NO
 *   Sparkline           | NO        | NO           | NO    (only own `color`/`height` props)
 *   DetailPanel         | NO        | NO           | NO
 *   FilterBar           | NO        | NO           | NO
 *
 * Conclusion: ZERO renderers honor ``props.style``. Most honor
 * ``props.className`` but NONE merge inline style. The bug is the
 * agent's expectation that gradient + color + textShadow specified
 * via ``props.style`` will paint — silently dropped at every
 * renderer's destructure boundary. Fix posture options (recorded in
 * the consult memory, NOT applied in this canary):
 *   (A) Wrap ``ComponentRenderer`` once in a top-level ``<div
 *       style={node.props.style} className={node.props.className}>``
 *       so every type gets pass-through for free.
 *   (B) Plumb ``style`` (and reaffirm ``className``) into every
 *       renderer's root element. More invasive; preserves semantic
 *       tag (``<Card>``, ``<button>``, ``<table>``).
 *   (C) Document an explicit prop allowlist in the catalog and
 *       teach the agent to STOP emitting raw style/className and
 *       instead use semantic props (``variant``, ``intent``, etc).
 *
 * Tests below:
 *   • RED — pin the bug for renderers that drop ``style`` outright.
 *   • RED — pin the bug for renderers that drop ``className`` (a
 *     few do, see matrix).
 *   • GREEN — pin the contract that DOES work today
 *     (``className`` for Card/Text/Alert/etc), so a future fix
 *     doesn't regress what's already correct.
 */

import React from "react";
import { describe, expect, it, vi } from "vitest";
import { render } from "@testing-library/react";
import { ComponentTree } from "../renderers/component-renderer";
import type { ReactAdapterNode } from "../renderers/renderer-types";

vi.mock("../renderers/use-tool-data", () => ({
  useToolData: () => ({ data: null, loading: false, error: null }),
}));

function node(
  type: string,
  props: Record<string, unknown>,
  children?: ReactAdapterNode[],
): ReactAdapterNode {
  return {
    id: `${type}-stylep`,
    component: type,
    originalType: type,
    props,
    children,
  };
}

function renderTree(nodes: ReactAdapterNode[]) {
  return render(<ComponentTree nodes={nodes} />);
}

const STYLE_NEEDLE = "rgb(255, 0, 153)"; // hot pink, easy to grep
const STYLE_INPUT = { color: STYLE_NEEDLE, background: "linear-gradient(180deg,#581c87,#f97316)" };
const CLASS_NEEDLE = "qa-decor-passthrough";

/** Walk the rendered tree and find ANY element with the passed inline-style declaration. */
function findStyledElement(container: HTMLElement, css: string, value: string): HTMLElement | null {
  const all = container.querySelectorAll<HTMLElement>("*");
  for (const el of Array.from(all)) {
    const v = el.style.getPropertyValue(css);
    if (v && v.replace(/\s/g, "").toLowerCase().includes(value.replace(/\s/g, "").toLowerCase())) {
      return el;
    }
  }
  return null;
}

/** Walk the rendered tree and find ANY element whose className contains the marker. */
function findClassedElement(container: HTMLElement, marker: string): HTMLElement | null {
  return container.querySelector<HTMLElement>(`[class*='${marker}']`);
}

/* ── style pass-through (RED until renderers plumb style) ───────── */

const STYLE_CASES: Array<[string, Record<string, unknown>]> = [
  ["Card", { title: "card-title", style: STYLE_INPUT }],
  ["Text", { text: "the-text", style: STYLE_INPUT }],
  ["Alert", { message: "the-alert", style: STYLE_INPUT }],
  ["Button", { label: "the-button", style: STYLE_INPUT }],
  ["Progress", { value: 50, style: STYLE_INPUT }],
  ["List", { items: ["a"], style: STYLE_INPUT }],
  ["Image", { src: "https://example.com/x.png", style: STYLE_INPUT }],
  ["Divider", { style: STYLE_INPUT }],
  ["Metric", { label: "L", value: "7", style: STYLE_INPUT }],
];

describe("A2UI renderer ↔ props.style pass-through (decorative-prop drop)", () => {
  for (const [type, props] of STYLE_CASES) {
    it(`${type}({style}) — root element carries inline color`, () => {
      const { container } = renderTree([node(type, props)]);
      const el = findStyledElement(container, "color", STYLE_NEEDLE);
      // RED: every renderer currently fails this assertion. See the
      // truth table in this file's docstring. Fixing one or both of
      // (A)/(B) above flips these to GREEN.
      expect(el, `${type} dropped props.style.color — expected an element with color: ${STYLE_NEEDLE}`).not.toBeNull();
    });
  }
});

/* ── className pass-through ──────────────────────────────────────
 *
 * Some renderers honor a string ``className`` from props (Card,
 * Text, etc). A few drop it entirely (Toast, StatusDot, TrendBadge,
 * Sparkline, DetailPanel, FilterBar, GraphViewer, ItemList). The
 * RED cases here pin the drop; the GREEN cases pin what works. */

const CLASS_CASES_PASSING: Array<[string, Record<string, unknown>]> = [
  // Already honor className today — pin the contract.
  ["Card", { title: "x", className: CLASS_NEEDLE }],
  ["Text", { text: "x", className: CLASS_NEEDLE }],
  ["Alert", { message: "x", className: CLASS_NEEDLE }],
  ["Button", { label: "x", className: CLASS_NEEDLE }],
  ["Progress", { value: 1, className: CLASS_NEEDLE }],
  ["List", { items: ["a"], className: CLASS_NEEDLE }],
  ["Image", { src: "https://example.com/x.png", className: CLASS_NEEDLE }],
  ["Divider", { className: CLASS_NEEDLE }],
  ["Metric", { label: "L", value: "1", className: CLASS_NEEDLE }],
];

const CLASS_CASES_DROPPING: Array<[string, Record<string, unknown>]> = [
  // RED today — these drop the className attribute on the floor.
  ["StatusDot", { value: 80, thresholds: { warning: 50 }, className: CLASS_NEEDLE }],
  ["TrendBadge", { direction: "up", change_pct: 5, className: CLASS_NEEDLE }],
  ["Sparkline", { data: [1, 2, 3], className: CLASS_NEEDLE }],
  ["FilterBar", { values: ["a", "b"], className: CLASS_NEEDLE }],
];

describe("A2UI renderer ↔ props.className pass-through", () => {
  for (const [type, props] of CLASS_CASES_PASSING) {
    it(`${type}({className}) — marker reaches DOM (GREEN baseline)`, () => {
      const { container } = renderTree([node(type, props)]);
      expect(findClassedElement(container, CLASS_NEEDLE)).not.toBeNull();
    });
  }
  for (const [type, props] of CLASS_CASES_DROPPING) {
    it(`${type}({className}) — marker reaches DOM (RED, currently dropped)`, () => {
      const { container } = renderTree([node(type, props)]);
      expect(
        findClassedElement(container, CLASS_NEEDLE),
        `${type} drops props.className silently — agent's tailwind hint is lost`,
      ).not.toBeNull();
    });
  }
});

/* ── Scene-level repro: the user's "Synthwave Arcade" surface ──
 *
 * One last canary that mirrors the actual round-6 user complaint:
 * agent paints a top-level Card with a gradient style and an
 * Alert with neon style — both should carry their decorative
 * inline styles to the DOM. RED today; FIXES make GREEN. */

describe("Synthwave Arcade scene parity (round-6 repro)", () => {
  it("top-level decorative Card + Alert keep style on root element", () => {
    const { container } = renderTree([
      node("Card", {
        title: "Sunset Sky",
        style: { background: "linear-gradient(180deg,#581c87,#f97316,#fbbf24)", height: "120px" },
      }),
      node("Alert", {
        message: "ARCADE ALERT",
        style: { color: STYLE_NEEDLE, borderColor: "#fbbf24" },
      }),
    ]);
    expect(
      findStyledElement(container, "background", "linear-gradient"),
      "Card with gradient sky background — empty white Card is the bug surface",
    ).not.toBeNull();
    expect(
      findStyledElement(container, "color", STYLE_NEEDLE),
      "Alert with neon color — appears as default styling instead",
    ).not.toBeNull();
  });
});
