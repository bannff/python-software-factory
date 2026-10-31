/**
 * Icon-token leak canary + metric-strip density
 * (bd:python-factory-3jcls.1 / bd:python-factory-3jcls.2).
 *
 * Bricks declare icons as DATA — either a heroicons-style kebab-case
 * token (``"icon": "cpu-chip"``) or a literal pictograph
 * (``"icon": "🔭"``). Before the fix, ``MetricCardRenderer`` and
 * ``ItemRow``'s ``SubtitleIcon`` interpolated the raw string, so the ML
 * Overview printed `cpu-chip`, `beaker`, `cube`,
 * `adjustments-horizontal`, `exclamation-triangle`, `arrow-path` as
 * right-aligned body text. Leaking an internal identifier into the UI
 * is the defect — an unmapped token must render NOTHING.
 *
 * These fail against the pre-fix renderers:
 *   • "unknown token renders no text" — the old fallback printed it.
 *   • "known token renders a glyph" — Metric had no ICON_MAP lookup at
 *     all, and several tokens bricks emit had no mapping.
 *   • "consecutive metrics tile into one grid" — they used to stack as
 *     full-width ~98px rows.
 */

import React from "react";
import { describe, expect, it, vi } from "vitest";
import { render } from "@testing-library/react";
import { ComponentTree, groupMetricRuns } from "../renderers/component-renderer";
import { ViewIcon, resolveIcon, isPictograph } from "../renderers/renderers-icon";
import { ICON_MAP } from "../renderers/renderers-item-list-icons";
import { ItemRow } from "../renderers/renderers-item-row";
import type { ReactAdapterNode } from "../renderers/renderer-types";

vi.mock("../renderers/use-tool-data", () => ({
  useToolData: () => ({ data: null, loading: false, error: null }),
}));

/** Every kebab-case token a brick declares somewhere in the repo. */
const DECLARED_TOKENS = [
  "cpu-chip", "beaker", "cube", "adjustments-horizontal",
  "exclamation-triangle", "arrow-path", "check-circle", "chart", "chart-bar",
  "chart-bar-square", "network", "pulse", "shield-check", "shield-exclamation",
  "server-stack", "document-text", "document", "users", "trophy",
  "rectangle-stack", "puzzle-piece", "play", "cube-transparent",
  "clipboard-document-list", "bolt", "bell", "banknotes", "circle-stack",
  "arrow-up-tray", "information-circle", "list",
];

const UNKNOWN_TOKENS = ["totally-made-up-icon", "some_unmapped_token", "sparkle-burst"];

function node(type: string, props: Record<string, unknown>, id = `${type}-icon`): ReactAdapterNode {
  return { id, component: type, originalType: type, props };
}

function glyphCount(container: HTMLElement): number {
  return container.querySelectorAll("svg").length;
}

/* ── ViewIcon resolution contract ─────────────────────────────────── */

describe("ViewIcon — brick-declared icon resolution", () => {
  for (const token of DECLARED_TOKENS) {
    it(`"${token}" resolves to a glyph and never leaks its text`, () => {
      const { container } = render(<ViewIcon name={token} />);
      expect(resolveIcon(token), `${token} has no ICON_MAP entry`).not.toBeNull();
      expect(glyphCount(container)).toBe(1);
      expect(container.textContent).toBe("");
    });
  }

  for (const token of UNKNOWN_TOKENS) {
    it(`unknown token "${token}" renders nothing — no identifier text`, () => {
      const { container } = render(<ViewIcon name={token} />);
      expect(container.textContent).toBe("");
      expect(glyphCount(container)).toBe(0);
    });
  }

  it("pictographs are their own glyph and still render as text", () => {
    const { container } = render(<ViewIcon name="🔭" />);
    expect(container.textContent).toBe("🔭");
    expect(isPictograph("🔭")).toBe(true);
    expect(isPictograph("cpu-chip")).toBe(false);
  });

  it("lookup is case- and underscore-tolerant", () => {
    expect(resolveIcon("CPU_CHIP")).toBe(ICON_MAP["cpu-chip"]);
  });

  it("empty / whitespace names render nothing", () => {
    const { container } = render(<><ViewIcon /><ViewIcon name="" /><ViewIcon name="   " /></>);
    expect(container.textContent).toBe("");
    expect(glyphCount(container)).toBe(0);
  });
});

/* ── Metric renderer — the ML Overview repro ──────────────────────── */

describe("MetricCardRenderer — icon token never reaches the DOM as text", () => {
  it("renders the ML Overview stat run without leaking any token", () => {
    const metrics = [
      ["Training Runs", "cpu-chip"], ["Experiments", "beaker"], ["Receipt Models", "cube"],
      ["Fine-Tuning Jobs", "adjustments-horizontal"], ["Regressions", "exclamation-triangle"],
      ["Learning Runs", "arrow-path"],
    ] as const;
    const { container } = render(
      <ComponentTree
        nodes={metrics.map(([label, icon], i) =>
          node("metric", { label, icon, value: String(i) }, `ml-overview-${i}`),
        )}
      />,
    );
    const text = container.textContent ?? "";
    for (const [label, icon] of metrics) {
      expect(text).toContain(label);
      expect(text, `leaked icon token "${icon}"`).not.toContain(icon);
    }
    expect(glyphCount(container)).toBe(metrics.length);
  });

  it("an unmapped metric icon renders no glyph and no text", () => {
    const { container } = render(
      <ComponentTree nodes={[node("metric", { label: "Widgets", icon: "not-a-real-icon", value: "4" })]} />,
    );
    expect(container.textContent).not.toContain("not-a-real-icon");
    expect(glyphCount(container)).toBe(0);
  });
});

/* ── ItemRow subtitle icon ────────────────────────────────────────── */

describe("ItemRow subtitle icon — no token fallback text", () => {
  const layout = { title: "$.name", subtitle_icon: "$.icon" };

  it("known token renders a glyph", () => {
    const { container } = render(
      <ItemRow item={{ name: "run-1", icon: "cpu-chip" }} itemKey="run-1" layout={layout}
        badgeColorMap={{}} isExpanded={false} onToggle={() => {}} />,
    );
    expect(container.textContent).not.toContain("cpu-chip");
    // chevron + subtitle glyph
    expect(glyphCount(container)).toBeGreaterThanOrEqual(2);
  });

  it("unknown token renders no text", () => {
    const { container } = render(
      <ItemRow item={{ name: "run-1", icon: "mystery-token" }} itemKey="run-1" layout={layout}
        badgeColorMap={{}} isExpanded={false} onToggle={() => {}} />,
    );
    expect(container.textContent).not.toContain("mystery-token");
  });
});

/* ── Metric strip density (bd:python-factory-3jcls.2) ─────────────── */

describe("ComponentTree — consecutive metrics tile into a responsive grid", () => {
  const metric = (i: number) => node("metric", { label: `m${i}`, value: String(i) }, `m-${i}`);

  it("groups a run of metrics and leaves other nodes alone", () => {
    const groups = groupMetricRuns([
      node("card", { title: "header" }, "hdr"),
      metric(1), metric(2), metric(3),
      node("chart", {}, "chart"),
      metric(4),
    ]);
    expect(groups.map((g) => g.kind)).toEqual(["single", "metrics", "single", "single"]);
    expect(groups[1].kind === "metrics" && groups[1].nodes).toHaveLength(3);
  });

  it("wraps the run in one grid container, not seven full-width rows", () => {
    const { container } = render(
      <ComponentTree nodes={[metric(1), metric(2), metric(3), metric(4), metric(5), metric(6), metric(7)]} />,
    );
    const strips = container.querySelectorAll("[data-metric-strip]");
    expect(strips).toHaveLength(1);
    expect(strips[0].className).toMatch(/\bgrid\b/);
    expect(strips[0].className).toMatch(/grid-cols-\d/);
    expect(strips[0].children).toHaveLength(7);
  });

  it("a lone metric keeps its original DOM shape (no grid wrapper)", () => {
    const { container } = render(<ComponentTree nodes={[metric(1)]} />);
    expect(container.querySelectorAll("[data-metric-strip]")).toHaveLength(0);
  });

  it("tiles are compact — no text-2xl value block", () => {
    const { container } = render(<ComponentTree nodes={[metric(1), metric(2)]} />);
    expect(container.innerHTML).not.toContain("text-2xl");
  });
});
