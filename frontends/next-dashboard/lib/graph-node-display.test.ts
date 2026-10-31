import test from "node:test";
import assert from "node:assert/strict";

const { deriveGraphNodeDisplayName } = await import(
  new URL("./graph-node-display.ts", import.meta.url).href,
);

test("deriveGraphNodeDisplayName prefers meaningful execution properties", () => {
  assert.equal(
    deriveGraphNodeDisplayName("tool-inv-abc12345", "ToolInvocation", { tool_name: "agent_reason" }),
    "agent_reason",
  );
  assert.equal(
    deriveGraphNodeDisplayName("session-abcdef12", "Session", { workflow_run_id: "run-12345678" }),
    "run:run-1234",
  );
  assert.equal(
    deriveGraphNodeDisplayName("agent-red", "Agent", { agent_id: "agent-red" }),
    "agent:agent-red",
  );
  assert.equal(
    deriveGraphNodeDisplayName("user-principal-7", "User", { principal_id: "principal-7" }),
    "user:principal-7",
  );
});

test("deriveGraphNodeDisplayName previews memory content, truncated past 48 chars", () => {
  assert.equal(
    deriveGraphNodeDisplayName("mem-1", "memory", { content: "prefers dark mode" }),
    "prefers dark mode",
  );
  const long = "x".repeat(60);
  assert.equal(
    deriveGraphNodeDisplayName("mem-2", "memory", { content: long }),
    `${"x".repeat(48)}…`,
  );
  assert.equal(
    deriveGraphNodeDisplayName("mem-3", "memory", {}),
    "mem-3",
  );
});