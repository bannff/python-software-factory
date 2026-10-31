/**
 * Sub-agent activity-renderer dispatcher canary (bd-6zyg).
 *
 * Validates the exported renderer objects have the activityType keys
 * the BE mapper emits, and that each renderer's Zod content schema
 * round-trips a sample payload from
 * ``components/ui/src/factory/ui/runtime/ag_ui_mapper_activity.py``.
 *
 * Pins the dispatcher predicate
 * ``rc.activityType === toolCall.activityType`` from
 * ``@copilotkitnext/react/dist/hooks/use-render-activity-message.mjs``.
 * The agentId-scoping chain (agentId-bound → unbound → wildcard) is
 * provider-level and verified separately in the dispatcher canary.
 */

import { describe, expect, it } from "vitest";
import {
  graphActivityRenderer,
  swarmActivityRenderer,
} from "../subagent-activity-renderer";

describe("subagent activity renderers (bd-6zyg)", () => {
  it("exports a swarm renderer keyed on subagent.swarm", () => {
    expect(swarmActivityRenderer.activityType).toBe("subagent.swarm");
    expect(typeof swarmActivityRenderer.render).toBe("function");
  });

  it("exports a graph renderer keyed on subagent.graph", () => {
    expect(graphActivityRenderer.activityType).toBe("subagent.graph");
    expect(typeof graphActivityRenderer.render).toBe("function");
  });

  it("dispatcher predicate (rc.activityType === message.activityType) selects the right renderer", () => {
    const renderers = [swarmActivityRenderer, graphActivityRenderer];

    function findRenderer(activityType: string) {
      return renderers.find((r) => r.activityType === activityType) ?? null;
    }

    expect(findRenderer("subagent.swarm")).toBe(swarmActivityRenderer);
    expect(findRenderer("subagent.graph")).toBe(graphActivityRenderer);
    expect(findRenderer("mcp-apps")).toBeNull();
  });

  it("swarm content Zod parses a backend-shape payload", () => {
    const payload = {
      activityType: "subagent.swarm",
      run_id: "tc-1",
      swarm_id: "tc-1",
      status: "running",
      agent_count: 2,
      nodes: [{ node_id: "scout", status: "running" }],
      started_at: 100.0,
    };
    const out = swarmActivityRenderer.content.safeParse(payload);
    expect(out.success).toBe(true);
  });

  it("graph content Zod parses a backend-shape payload with closed status", () => {
    const payload = {
      activityType: "subagent.graph",
      run_id: "tc-2",
      graph_id: "tc-2",
      status: "completed",
      nodes: [
        { node_id: "n1", status: "completed", stopped_at: 5.0 },
      ],
      started_at: 1.0,
      completed_at: 5.0,
    };
    const out = graphActivityRenderer.content.safeParse(payload);
    expect(out.success).toBe(true);
  });

  it("rejects payload with wrong activityType (discriminator mismatch)", () => {
    const payload = {
      activityType: "subagent.graph",
      run_id: "tc",
      swarm_id: "tc",
      status: "running",
      agent_count: 0,
      nodes: [],
      started_at: 1.0,
    };
    // swarm renderer should reject because activityType literal mismatches
    const out = swarmActivityRenderer.content.safeParse(payload);
    expect(out.success).toBe(false);
  });

  it("agentId-scoping chain — unbound matches when no agentId-bound renderer exists", () => {
    // Mirrors @copilotkitnext/react use-render-activity-message.mjs:
    //   matches.find(c => c.agentId === agentId)
    //     ?? matches.find(c => c.agentId === undefined)
    //     ?? renderers.find(c => c.activityType === "*")
    //     ?? null
    const agentId = "default";
    const r = swarmActivityRenderer as { agentId?: string };
    const matches = [r];
    const picked =
      matches.find((c) => c.agentId === agentId) ??
      matches.find((c) => c.agentId === undefined) ??
      null;
    expect(picked).toBe(swarmActivityRenderer);
  });
});
