import test from "node:test";
import assert from "node:assert/strict";

const {
  mapLiveActivityEvent,
  mapLiveToolEvent,
} = await import(new URL("./live-tool-events.ts", import.meta.url).href);

test("mapLiveToolEvent preserves workflow and session identity", () => {
  const entry = mapLiveToolEvent({
    brick: "agent",
    tool: "agent_reason",
    success: true,
    latency_ms: 12.5,
    ts: 1715600000,
    session_id: "session-42",
    workflow_run_id: "run-42",
    caller: "principal-7",
    args_summary: { task: "scan" },
    result_summary: { status: "ok" },
  }, "evt-1");

  assert.equal(entry.workflow_run_id, "run-42");
  assert.equal(entry.session_id, "session-42");
  assert.equal(entry.caller, "principal-7");
  assert.deepEqual(entry.args_summary, { task: "scan" });
});

test("mapLiveActivityEvent preserves run identity from activity payload", () => {
  const entry = mapLiveActivityEvent({
    event_type: "swarm.completed",
    source: "agent",
    ts: 1715600001,
    payload: {
      swarm_id: "redteam-scan",
      run_id: "run-99",
      session_id: "session-99",
    },
  }, "evt-2");

  assert.equal(entry.workflow_run_id, "run-99");
  assert.equal(entry.session_id, "session-99");
  assert.equal(entry.detail, "redteam-scan");
  assert.equal(entry.status, "completed");
});

test("mapLiveActivityEvent maps canonical Workflow stream metadata safely", () => {
  const entry = mapLiveActivityEvent({
    event_type: "workflow.attempt_stream_event",
    source: "workflow",
    ts: 1715600003,
    payload: {
      run_id: "wfr:v1:durable",
      attempt_id: "attempt-1",
      native_event_type: "multiagent_node_stream",
      node_id: "reviewer",
    },
  }, "evt-4");

  assert.equal(entry.title, "Workflow attempt stream · multiagent_node_stream");
  assert.equal(entry.detail, "multiagent_node_stream · reviewer");
  assert.equal(entry.status, "running");
  assert.equal(entry.workflow_run_id, "wfr:v1:durable");
});

test("mapLiveActivityEvent maps canonical Workflow terminal statuses", () => {
  const cases = [
    ["workflow.run_succeeded", "completed", "Workflow run succeeded"],
    ["workflow.run_failed", "failed", "Workflow run failed"],
    ["workflow.run_cancelled", "completed", "Workflow run cancelled"],
    ["workflow.attempt_completed", "failed", "Workflow attempt completed"],
  ] as const;
  for (const [event_type, status, title] of cases) {
    const entry = mapLiveActivityEvent({
      event_type, source: "workflow", ts: 1715600004,
      payload: { run_id: "wfr:v1:terminal", status: event_type === "workflow.attempt_completed" ? "failed" : status },
    }, event_type);
    assert.equal(entry.status, status);
    assert.equal(entry.title, title);
  }
});

test("mapLiveActivityEvent maps RL milestones into a readable timeline entry", () => {
  const entry = mapLiveActivityEvent({
    event_type: "rl.scored",
    source: "games",
    ts: 1715600002,
    payload: {
      workflow_run_id: "run-77",
      session_id: "session-77",
      f1: 0.83,
      workflow_type: "dast",
      target_app: "webgoat",
      vuln_class: "IDOR",
    },
  }, "evt-3");

  assert.equal(entry.title, "RL scored");
  assert.equal(entry.status, "completed");
  assert.equal(entry.workflow_run_id, "run-77");
  assert.equal(entry.session_id, "session-77");
  assert.equal(entry.detail, "F1 0.83");
});