import test from "node:test";
import assert from "node:assert/strict";

const {
  summarizeRuntimeMetrics,
} = await import(new URL("./runtime-metrics-summary.ts", import.meta.url).href);

test("summarizeRuntimeMetrics counts RL runs and latest score by workflow_run_id", () => {
  const summary = summarizeRuntimeMetrics([
    {
      id: "tool-1",
      type: "tool_call",
      title: "agent_reason",
      status: "completed",
      timestamp: 1715600000,
      duration: 42,
      detail: "agent",
    },
    {
      id: "rl-1",
      type: "swarm_event",
      title: "RL started",
      status: "running",
      timestamp: 1715600001,
      workflow_run_id: "run-1",
      swarmEventType: "rl.started",
      swarmMeta: { workflow_type: "dast", target_app: "webgoat", vuln_class: "IDOR" },
    },
    {
      id: "rl-2",
      type: "swarm_event",
      title: "RL scored",
      status: "completed",
      timestamp: 1715600002,
      workflow_run_id: "run-1",
      swarmEventType: "rl.scored",
      swarmMeta: { workflow_type: "dast", target_app: "webgoat", vuln_class: "IDOR", f1: 0.83 },
    },
    {
      id: "rl-3",
      type: "swarm_event",
      title: "RL completed",
      status: "completed",
      timestamp: 1715600003,
      workflow_run_id: "run-1",
      swarmEventType: "rl.completed",
      swarmMeta: { workflow_type: "dast", target_app: "webgoat", vuln_class: "IDOR" },
    },
    {
      id: "rl-4",
      type: "swarm_event",
      title: "RL failed",
      status: "failed",
      timestamp: 1715600004,
      workflow_run_id: "run-2",
      swarmEventType: "rl.failed",
      swarmMeta: { workflow_type: "sast", target_app: "juice-shop", vuln_class: "XSS" },
    },
  ]);

  assert.equal(summary.toolCalls, 1);
  assert.equal(summary.rlEvents, 4);
  assert.equal(summary.rlRuns, 2);
  assert.equal(summary.rlCompletedRuns, 1);
  assert.equal(summary.rlFailedRuns, 1);
  assert.equal(summary.latestRlScore, 0.83);
  assert.equal(summary.latestRlRunId, "run-1");
  assert.equal(summary.latestRlContext, "dast · webgoat · IDOR");
});

test("summarizeRuntimeMetrics prefers domain_class over vuln_class for latestRlContext (bd:python-factory-ttru9)", () => {
  // Both fields present → domain_class wins. Mirrors the BE
  // back-compat pattern from hadbi.qer1z (game_pipeline.py::
  // _store_learnings) where domain_class is the new canonical field
  // and vuln_class is the legacy alias.
  const summary = summarizeRuntimeMetrics([
    {
      id: "rl-domain-1",
      type: "swarm_event",
      title: "RL scored",
      status: "completed",
      timestamp: 1715600100,
      workflow_run_id: "run-domain",
      swarmEventType: "rl.scored",
      swarmMeta: {
        workflow_type: "wine_pairing_eval",
        target_app: "sommelier-bot",
        domain_class: "wine_pairing",
        vuln_class: "IDOR",
        f1: 0.71,
      },
    },
  ]);

  assert.equal(summary.latestRlContext, "wine_pairing_eval · sommelier-bot · wine_pairing");
});

test("summarizeRuntimeMetrics falls back to vuln_class when domain_class is missing (bd:python-factory-ttru9 back-compat)", () => {
  // Only vuln_class present (legacy BE event shape pre-hadbi.qer1z).
  // Display string must still render the legacy value.
  const summary = summarizeRuntimeMetrics([
    {
      id: "rl-legacy-1",
      type: "swarm_event",
      title: "RL scored",
      status: "completed",
      timestamp: 1715600200,
      workflow_run_id: "run-legacy",
      swarmEventType: "rl.scored",
      swarmMeta: {
        workflow_type: "dast",
        target_app: "webgoat",
        vuln_class: "IDOR",
        f1: 0.6,
      },
    },
  ]);

  assert.equal(summary.latestRlContext, "dast · webgoat · IDOR");
});

test("summarizeRuntimeMetrics uses domain_class when vuln_class is absent (bd:python-factory-ttru9 forward path)", () => {
  // Only domain_class present (post-cutover BE event shape with no
  // vuln_class alias). Must render domain_class as the third bit.
  const summary = summarizeRuntimeMetrics([
    {
      id: "rl-domain-only",
      type: "swarm_event",
      title: "RL scored",
      status: "completed",
      timestamp: 1715600300,
      workflow_run_id: "run-forward",
      swarmEventType: "rl.scored",
      swarmMeta: {
        workflow_type: "dast",
        target_app: "petstore",
        domain_class: "broken_auth",
        f1: 0.55,
      },
    },
  ]);

  assert.equal(summary.latestRlContext, "dast · petstore · broken_auth");
});