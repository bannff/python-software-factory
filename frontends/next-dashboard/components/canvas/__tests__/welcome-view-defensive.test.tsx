/**
 * Welcome-view defensive metric strip canary
 * (bd:python-factory-d4r37 — substrate-prep follow-up to epic
 * python-factory-hadbi).
 *
 * The status strip in `welcome-view.tsx` calls three brick tools
 * (`security_security.list_persisted_findings`, `evals_list_run_results`,
 * `graph_get_stats`) on mount. If a future domain project drops the
 * security brick from its `pyproject.toml`, the gateway returns a
 * 404 / brick-missing response and the metric promise rejects. Pre-fix
 * that rejection bubbled out of `Promise.allSettled` (the `.then`
 * chain swallowed the value but not the error) and the dashboard
 * crashed.
 *
 * This canary mocks `@/lib/api` so the security call rejects while
 * the other two resolve. The view must:
 *   1. render without throwing,
 *   2. show "—" for the findings metric (graceful degradation),
 *   3. continue showing the eval pass-rate + graph-nodes values that
 *      did resolve.
 *
 * The renderer in welcome-view.tsx (around lines 138–144) shows "—"
 * either when `metric.loading === true` or when `metric.value == null`.
 * After the catch fires, `loading` flips false and `value` is `null`,
 * so the displayed glyph is the same "—" but for the post-load reason.
 */

import * as React from "react";
import { describe, expect, it, vi, beforeEach, afterEach } from "vitest";
import { act, render, screen, waitFor } from "@testing-library/react";

vi.mock("@/lib/api", () => ({
  callTool: vi.fn(),
}));

vi.mock("@/lib/hooks/use-live-tool-stream", () => ({
  useLiveToolStream: () => ({
    entries: [],
    connected: true,
    frozen: false,
    setFrozen: () => {},
  }),
}));

// ParticleText pulls in framer-motion text effects we don't need to
// exercise here — stub to a plain span so the test stays focused on
// metric-strip behavior.
vi.mock("@/components/ui/particle-text", () => ({
  ParticleText: ({ words }: { words: string[] }) => (
    <span data-testid="particle-text">{words[0]}</span>
  ),
}));

import { callTool } from "@/lib/api";
import WelcomeView from "../welcome-view";

const mockedCallTool = callTool as unknown as ReturnType<typeof vi.fn>;

describe("WelcomeView metric strip defensive call (bd:python-factory-d4r37)", () => {
  beforeEach(() => {
    mockedCallTool.mockReset();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("renders without throwing when security_security.list_persisted_findings rejects", async () => {
    mockedCallTool.mockImplementation((name: string) => {
      if (name === "security_security.list_persisted_findings") {
        return Promise.reject(new Error("brick 'security' not loaded"));
      }
      if (name === "evals_list_run_results") {
        return Promise.resolve({ result: { latest: { pass_rate: 0.9 } } });
      }
      if (name === "graph_get_stats") {
        return Promise.resolve({ result: { node_count: 42 } });
      }
      return Promise.reject(new Error(`unexpected tool ${name}`));
    });

    await act(async () => {
      render(<WelcomeView />);
    });

    // Wait for the eval and graph metrics to settle to their resolved
    // values. The findings metric should *also* have settled (to "—")
    // because the catch ran graceful-degradation.
    await waitFor(() => {
      expect(screen.getByText("90%")).toBeTruthy();
      expect(screen.getByText("42")).toBeTruthy();
    });

    // Findings label is present and its value renders as "—" rather
    // than crashing the component.
    expect(screen.getByText("findings")).toBeTruthy();
    // Both metric loading-glyph and the post-fail null glyph render as
    // "—". After waitFor the whole strip has resolved, so the only
    // "—" left in the strip belongs to the findings metric.
    const dashes = screen.getAllByText("—");
    expect(dashes.length).toBeGreaterThanOrEqual(1);
  });

  it("renders the findings count when security tool resolves (positive path)", async () => {
    mockedCallTool.mockImplementation((name: string) => {
      if (name === "security_security.list_persisted_findings") {
        return Promise.resolve({ result: { count: 7 } });
      }
      if (name === "evals_list_run_results") {
        return Promise.resolve({ result: { latest: { pass_rate: 0.9 } } });
      }
      if (name === "graph_get_stats") {
        return Promise.resolve({ result: { node_count: 42 } });
      }
      return Promise.reject(new Error(`unexpected tool ${name}`));
    });

    await act(async () => {
      render(<WelcomeView />);
    });

    await waitFor(() => {
      expect(screen.getByText("7")).toBeTruthy();
      expect(screen.getByText("90%")).toBeTruthy();
      expect(screen.getByText("42")).toBeTruthy();
    });
  });

  it("renders without throwing when all three tools reject (graph-only / minimal-loadout substrate)", async () => {
    mockedCallTool.mockImplementation(() =>
      Promise.reject(new Error("brick not loaded")),
    );

    await act(async () => {
      render(<WelcomeView />);
    });

    // All three metric labels still rendered, but their values fall
    // back to "—" without the component throwing.
    await waitFor(() => {
      expect(screen.getByText("findings")).toBeTruthy();
      expect(screen.getByText("eval pass rate")).toBeTruthy();
      expect(screen.getByText("graph nodes")).toBeTruthy();
    });
    // At least three "—" glyphs in the metric strip (one per metric).
    await waitFor(() => {
      const dashes = screen.getAllByText("—");
      expect(dashes.length).toBeGreaterThanOrEqual(3);
    });
  });
});
