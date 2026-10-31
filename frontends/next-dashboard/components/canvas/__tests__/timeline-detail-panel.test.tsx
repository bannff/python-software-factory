import { describe, it, expect } from "vitest";
import { render } from "@testing-library/react";
import { TimelineDetailPanel } from "../timeline-detail-panel";
import type { TimelineEntry } from "@/lib/types";

const FULL_ENTRY: TimelineEntry = {
  id: "full-test-1",
  type: "tool_call",
  title: "scan_resource",
  status: "failed",
  timestamp: 1719000000000,
  duration: 2345,
  detail: "security",
  severity: "high",
  error: "ConnectionTimeout: host unreachable",
  workflow_run_id: "run-abc12345-def6",
  session_id: "sess-xyz98765-ghi0",
  agent_id: "agent-alpha",
  principal_id: "user-daniel",
  caller: "orchestrator.main",
  swarmEventType: "node_start",
  swarmMeta: { target_node: "scanner-1", depth: 2 },
  args_summary: { resource_arn: "arn:aws:s3:::bucket", mode: "deep" },
  result_summary: { status: "error", items_scanned: 0 },
};

describe("TimelineDetailPanel - field completeness", () => {
  it("renders all populated TimelineEntry fields", () => {
    const { container } = render(
      <TimelineDetailPanel entry={FULL_ENTRY} isNew={false} />,
    );
    const text = container.textContent ?? "";

    // Core fields
    expect(text).toContain("scan_resource"); // title/tool
    expect(text).toContain("failed"); // status
    expect(text).toContain("security"); // detail/brick
    expect(text).toContain("tool_call"); // type
    expect(text).toContain("2.3s"); // duration formatted
    expect(text).toContain("hist"); // source

    // Identity fields
    expect(text).toContain("orchestrator.main"); // caller
    expect(text).toContain("agent-alpha"); // agent_id
    expect(text).toContain("user-daniel"); // principal_id
    expect(text).toContain("sess-xyz98765-ghi0"); // session_id
    expect(text).toContain("run-abc12345-def6"); // workflow_run_id

    // Severity
    expect(text).toContain("high");

    // Swarm
    expect(text).toContain("node_start"); // swarmEventType
    expect(text).toContain("target_node"); // swarmMeta key
    expect(text).toContain("scanner-1"); // swarmMeta value

    // Args
    expect(text).toContain("resource_arn");
    expect(text).toContain("arn:aws:s3:::bucket");

    // Result
    expect(text).toContain("items_scanned");

    // Error
    expect(text).toContain("ConnectionTimeout: host unreachable");
  });

  it("renders live source for new entries", () => {
    const { container } = render(
      <TimelineDetailPanel entry={FULL_ENTRY} isNew={true} />,
    );
    expect(container.textContent).toContain("live");
  });

  it("omits optional fields gracefully when absent", () => {
    const minimal: TimelineEntry = {
      id: "min-1",
      type: "step",
      title: "noop",
      status: "completed",
      timestamp: Date.now(),
    };
    const { container } = render(
      <TimelineDetailPanel entry={minimal} isNew={false} />,
    );
    const text = container.textContent ?? "";
    expect(text).toContain("noop");
    expect(text).toContain("completed");
    // Should NOT contain labels for absent fields
    expect(text).not.toContain("caller:");
    expect(text).not.toContain("agent:");
    expect(text).not.toContain("severity:");
    expect(text).not.toContain("error:");
  });
});
