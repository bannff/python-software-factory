/**
 * Runtime-metrics-summary `domain_class` precedence canary
 * (bd:python-factory-ttru9 — substrate-prep follow-up to epic
 * python-factory-hadbi).
 *
 * After hadbi.qer1z BE now emits `domain_class` on swarm events with
 * `vuln_class` as the back-compat alias (mirrors the BE fallback in
 * `components/games/.../game_pipeline.py::_store_learnings`). The
 * dashboard's `latestRlContext` display string must read
 * `domain_class` first and fall back to `vuln_class`.
 *
 * Note: there's a parallel `lib/runtime-metrics-summary.test.ts` that
 * uses `node:test` for the same logic — that file exists outside the
 * vitest glob and is not part of `npm run test`. This canary lives
 * inside `__tests__/` so it's picked up by the project's actual
 * Vitest quality gate.
 */

import { describe, expect, it } from "vitest";
import { summarizeRuntimeMetrics } from "../runtime-metrics-summary";
import type { TimelineEntry } from "../types";

function rlScoredEntry(meta: Record<string, unknown>): TimelineEntry {
  return {
    id: "rl-1",
    type: "swarm_event",
    title: "RL scored",
    status: "completed",
    timestamp: 1715600002,
    workflow_run_id: "run-1",
    swarmEventType: "rl.scored",
    swarmMeta: { f1: 0.83, ...meta },
  } as TimelineEntry;
}

describe("summarizeRuntimeMetrics — latestRlContext domain_class precedence", () => {
  it("renders domain_class when both fields are present (domain_class wins)", () => {
    // bd:python-factory-ttru9 acceptance criterion:
    //   {domain_class: 'wine_pairing', vuln_class: 'IDOR'} displays
    //   'wine_pairing'.
    const summary = summarizeRuntimeMetrics([
      rlScoredEntry({
        workflow_type: "wine_pairing_eval",
        target_app: "sommelier-bot",
        domain_class: "wine_pairing",
        vuln_class: "IDOR",
      }),
    ]);
    expect(summary.latestRlContext).toBe(
      "wine_pairing_eval · sommelier-bot · wine_pairing",
    );
  });

  it("falls back to vuln_class when domain_class is missing (legacy BE shape)", () => {
    // Pre-hadbi.qer1z events only carry `vuln_class`. Display must
    // still render that legacy value so historical timeline frames
    // are readable.
    const summary = summarizeRuntimeMetrics([
      rlScoredEntry({
        workflow_type: "dast",
        target_app: "webgoat",
        vuln_class: "IDOR",
      }),
    ]);
    expect(summary.latestRlContext).toBe("dast · webgoat · IDOR");
  });

  it("renders domain_class when vuln_class is absent (forward-only path)", () => {
    // Post-cutover events drop the legacy alias entirely. Must
    // render the canonical `domain_class` value.
    const summary = summarizeRuntimeMetrics([
      rlScoredEntry({
        workflow_type: "dast",
        target_app: "petstore",
        domain_class: "broken_auth",
      }),
    ]);
    expect(summary.latestRlContext).toBe("dast · petstore · broken_auth");
  });

  it("ignores empty-string domain_class and falls back to vuln_class", () => {
    // Defensive case: BE emits an empty string for `domain_class`
    // (e.g. cleared at config-read time). The fallback must engage.
    const summary = summarizeRuntimeMetrics([
      rlScoredEntry({
        workflow_type: "dast",
        target_app: "webgoat",
        domain_class: "",
        vuln_class: "IDOR",
      }),
    ]);
    expect(summary.latestRlContext).toBe("dast · webgoat · IDOR");
  });

  it("returns workflow_run_id when neither class field is present", () => {
    // Nothing taxonomic to render — fall back to the run id so the
    // UI still shows *something* identifiable.
    const summary = summarizeRuntimeMetrics([
      rlScoredEntry({}),
    ]);
    expect(summary.latestRlContext).toBe("run-1");
  });
});
