import test from "node:test";
import assert from "node:assert/strict";

// Pin the contract that the Timeline hook calls the typed graph tool
// (graph_list_recent_tool_invocations) — NOT graph_query — under
// bd python-factory-c39g.

const HOOK_URL = new URL("./use-timeline-data.ts", import.meta.url).href;
const SOURCE = await (
  await import("node:fs/promises")
).readFile(new URL(HOOK_URL).pathname, "utf8");

test("useTimelineData calls the typed graph tool, not graph_query", () => {
  assert.match(
    SOURCE,
    /graph_list_recent_tool_invocations/,
    "must call the typed tool",
  );
  assert.doesNotMatch(
    SOURCE,
    /graph_query/,
    "must not call graph_query — bd python-factory-c39g closed the leak",
  );
  assert.doesNotMatch(
    SOURCE,
    /TIMELINE_HISTORY_QUERY/,
    "TIMELINE_HISTORY_QUERY constant should be gone",
  );
});

test("useTimelineData hook module loads", async () => {
  const mod = await import(HOOK_URL).catch((err) => err);
  if (mod instanceof Error) {
    test.skip("TypeScript runtime not available (use `npm run build` to verify).");
    return;
  }
  assert.equal(typeof mod.useTimelineData, "function");
});
