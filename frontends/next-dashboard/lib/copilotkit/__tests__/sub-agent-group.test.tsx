/**
 * groupMessageElements() canary (bd:python-factory-esb6n).
 *
 * The pure partition function decides which message elements render bare
 * (coordinator) vs inside a sub-agent containment box. Grouping is
 * POSITIONAL, anchored on the SYNC spawn tool-call id (tcid), NOT on a
 * `subagent-`/`swarm-` message-id prefix. All four sync spawns
 * (spawn_subagent / spawn_swarm / spawn_graph / spawn_registered_graph)
 * form a box. These cases pin the contract so a future change can't
 * silently re-leak sub-agent output (reasoning, prose, tool calls) back
 * into the main chat flow.
 *
 * Mirrors the live streams captured in `.scratch/esb6n-live-diagnosis.md`:
 * spawn(tcid) → sub-agent reasoning (plain uuid) → swarm-<node>/subagent-<tcid>
 * prose → bare tooluse_* sub-agent calls (incl handoff_to_agent) + tool
 * results → spawn's own tool-result (toolCallId===tcid, the done boundary)
 * → coordinator summary.
 */

import React from "react";
import { describe, expect, it } from "vitest";
import type { Message } from "@ag-ui/core";
import { groupMessageElements } from "../sub-agent-grouping";

interface AsstOpts {
  /** spawn_subagent agent_id (shorthand for a single-agent spawn). */
  spawn?: string;
  /** Arbitrary spawn tool name + args, for swarm/graph/registered cases. */
  spawnTool?: string;
  spawnArgs?: Record<string, unknown>;
  tcid?: string;
  text?: string;
  tool?: string;
}

/** Assistant message. Either a spawn (spawn/spawnTool) or a plain tool call. */
function asst(id: string, opts: AsstOpts = {}): Message {
  const m: Record<string, unknown> = { id, role: "assistant" };
  if (opts.text) m.content = opts.text;
  if (opts.spawn || opts.spawnTool) {
    m.toolCalls = [
      {
        id: opts.tcid ?? `tc-${id}`,
        type: "function",
        function: {
          name: opts.spawnTool ?? "spawn_subagent",
          arguments: JSON.stringify(
            opts.spawnArgs ?? { agent_id: opts.spawn },
          ),
        },
      },
    ];
  } else if (opts.tool) {
    m.toolCalls = [
      {
        id: opts.tcid ?? `tc-${id}`,
        type: "function",
        function: { name: opts.tool, arguments: "{}" },
      },
    ];
  }
  return m as Message;
}

function reasoning(id: string): Message {
  return { id, role: "reasoning", content: "thinking…" } as Message;
}

function toolResult(id: string, toolCallId: string): Message {
  return { id, role: "tool", toolCallId, content: "result" } as Message;
}

function user(id: string): Message {
  return { id, role: "user", content: "hi" } as Message;
}

/** A stand-in element keyed by message id (mirrors CopilotKit's keying). */
function el(key: string): React.ReactElement {
  return React.createElement("div", { key });
}

describe("groupMessageElements", () => {
  it("passes coordinator messages through bare", () => {
    const messages = [user("u1"), asst("a1", { text: "hello" })];
    const elements = [el("u1"), el("a1")];
    const runs = groupMessageElements(messages, elements);
    expect(runs).toHaveLength(2);
    expect(runs.every((r) => r.kind === "coordinator")).toBe(true);
  });

  it("groups a single spawn + its sub-agent prose into one box", () => {
    const messages = [
      user("u1"),
      asst("spawn1", { spawn: "eval-runner", tcid: "tcid1" }),
      asst("subagent-tcid1", { text: "done" }),
    ];
    const elements = messages.map((m) => el(m.id));
    const runs = groupMessageElements(messages, elements);
    const boxes = runs.filter((r) => r.kind === "subagent");
    expect(boxes).toHaveLength(1);
    expect(boxes[0].kind === "subagent" && boxes[0].agentId).toBe(
      "Sub-agent · eval-runner",
    );
    // spawn element + prose element
    expect(boxes[0].kind === "subagent" && boxes[0].elements).toHaveLength(2);
  });

  it("absorbs UNPREFIXED sub-agent reasoning into the box (text-leak fix)", () => {
    // The live bug: a sub-agent reasoning message carries a plain UUID
    // (no subagent- prefix, bd-ckihm gap). The old prefix gate ejected it
    // and everything after; positional grouping must keep it inside.
    const messages = [
      asst("spawn1", { spawn: "eval-runner", tcid: "tcid1" }),
      reasoning("plain-uuid-reasoning"),
      asst("subagent-tcid1", { text: "the answer" }),
      toolResult("r-spawn", "tcid1"),
    ];
    const elements = messages.map((m) => el(m.id));
    const runs = groupMessageElements(messages, elements);
    expect(runs).toHaveLength(1);
    expect(runs[0].kind).toBe("subagent");
    // spawn + reasoning + prose + spawn-result all inside the one box
    expect(runs[0].kind === "subagent" && runs[0].elements).toHaveLength(4);
  });

  it("absorbs bare tooluse_* sub-agent tool calls (no subagent- prefix)", () => {
    const messages = [
      asst("spawn1", { spawn: "eval-runner", tcid: "tcid1" }),
      asst("tooluse_AAA", { tool: "evals_list_run_results", tcid: "tooluse_AAA" }),
      toolResult("res-AAA", "tooluse_AAA"),
      asst("subagent-tcid1", { text: "summary" }),
      toolResult("r-spawn", "tcid1"),
    ];
    const elements = messages.map((m) => el(m.id));
    const runs = groupMessageElements(messages, elements);
    expect(runs).toHaveLength(1);
    expect(runs[0].kind).toBe("subagent");
    expect(runs[0].kind === "subagent" && runs[0].elements).toHaveLength(5);
  });

  it("closes the box AFTER the spawn's own tool-result; coordinator stays out", () => {
    const messages = [
      asst("spawn1", { spawn: "eval-runner", tcid: "tcid1" }),
      asst("subagent-tcid1", { text: "sub result" }),
      toolResult("r-spawn", "tcid1"), // done boundary
      asst("coord1", { text: "Here is my summary" }),
    ];
    const elements = messages.map((m) => el(m.id));
    const runs = groupMessageElements(messages, elements);
    expect(runs).toHaveLength(2);
    expect(runs[0].kind).toBe("subagent");
    // spawn + prose + spawn-result inside; coordinator outside
    expect(runs[0].kind === "subagent" && runs[0].elements).toHaveLength(3);
    expect(runs[1].kind).toBe("coordinator");
    expect(runs[1].key).toBe("coord1");
  });

  it("closes BEFORE coordinator prose when the spawn result never arrives", () => {
    // Defensive fallback: stream cut short, no role:tool for tcid.
    const messages = [
      asst("spawn1", { spawn: "eval-runner", tcid: "tcid1" }),
      asst("subagent-tcid1", { text: "sub result" }),
      asst("coord1", { text: "Here is my summary" }),
    ];
    const elements = messages.map((m) => el(m.id));
    const runs = groupMessageElements(messages, elements);
    expect(runs).toHaveLength(2);
    expect(runs[0].kind).toBe("subagent");
    expect(runs[0].kind === "subagent" && runs[0].elements).toHaveLength(2);
    expect(runs[1].kind).toBe("coordinator");
  });

  it("makes two sequential spawns into two separate boxes", () => {
    const messages = [
      asst("spawn1", { spawn: "security-analyst", tcid: "tcid1" }),
      asst("subagent-tcid1", { text: "a" }),
      toolResult("r1", "tcid1"),
      asst("spawn2", { spawn: "eval-runner", tcid: "tcid2" }),
      asst("subagent-tcid2", { text: "b" }),
      toolResult("r2", "tcid2"),
    ];
    const elements = messages.map((m) => el(m.id));
    const runs = groupMessageElements(messages, elements);
    const boxes = runs.filter((r) => r.kind === "subagent");
    expect(boxes).toHaveLength(2);
    expect(boxes[0].kind === "subagent" && boxes[0].agentId).toBe(
      "Sub-agent · security-analyst",
    );
    expect(boxes[1].kind === "subagent" && boxes[1].agentId).toBe(
      "Sub-agent · eval-runner",
    );
  });

  it("starts a fresh box when a second spawn immediately follows", () => {
    // No tool-result between spawns — the new spawn must close the prior box.
    const messages = [
      asst("spawn1", { spawn: "a", tcid: "t1" }),
      asst("spawn2", { spawn: "b", tcid: "t2" }),
    ];
    const elements = messages.map((m) => el(m.id));
    const runs = groupMessageElements(messages, elements);
    expect(runs).toHaveLength(2);
    expect(runs.every((r) => r.kind === "subagent")).toBe(true);
  });

  it("preserves element identity by reference", () => {
    const e1 = el("spawn1");
    const messages = [asst("spawn1", { spawn: "eval-runner", tcid: "tcid1" })];
    const runs = groupMessageElements(messages, [e1]);
    expect(runs[0].kind === "subagent" && runs[0].elements[0]).toBe(e1);
  });

  // ---- multi-agent spawns (bd:python-factory-esb6n follow-up) -------------

  it("boxes a spawn_swarm run — all node work in one box, labeled by count", () => {
    // Mirrors the live swarm stream: spawn_swarm → node reasoning →
    // swarm-<node> prose → bare node tool call → handoff_to_agent → next
    // node reasoning + prose + tool → spawn's own tool-result closes.
    const messages = [
      asst("swarmspawn", {
        spawnTool: "spawn_swarm",
        spawnArgs: { agent_ids: ["eval-runner", "security-analyst"] },
        tcid: "KVM",
      }),
      reasoning("node1-reasoning"),
      asst("swarm-eval-runner", { text: "node 1 prose" }),
      asst("tooluse_n1", { tool: "evals_list_runs", tcid: "tooluse_n1" }),
      toolResult("r-n1", "tooluse_n1"),
      asst("tooluse_ho", { tool: "handoff_to_agent", tcid: "tooluse_ho" }),
      toolResult("r-ho", "tooluse_ho"),
      reasoning("node2-reasoning"),
      asst("swarm-security-analyst", { text: "node 2 prose" }),
      asst("tooluse_n2", { tool: "security_list_persisted_findings", tcid: "tooluse_n2" }),
      toolResult("r-n2", "tooluse_n2"),
      toolResult("r-swarm", "KVM"), // spawn_swarm's own result — done boundary
      asst("coord", { text: "Both agents reported." }),
    ];
    const elements = messages.map((m) => el(m.id));
    const runs = groupMessageElements(messages, elements);
    const boxes = runs.filter((r) => r.kind === "subagent");
    expect(boxes).toHaveLength(1);
    expect(boxes[0].kind === "subagent" && boxes[0].agentId).toBe(
      "Swarm · 2 agents",
    );
    // everything from spawn through the swarm tool-result (12 msgs) inside;
    // only the coordinator summary outside.
    expect(boxes[0].kind === "subagent" && boxes[0].elements).toHaveLength(12);
    expect(runs[runs.length - 1].kind).toBe("coordinator");
  });

  it("boxes a spawn_graph run labeled by node count", () => {
    const messages = [
      asst("graphspawn", {
        spawnTool: "spawn_graph",
        spawnArgs: { agent_ids: ["recon", "exploit", "report"] },
        tcid: "G1",
      }),
      asst("swarm-recon", { text: "recon prose" }),
      toolResult("r-graph", "G1"),
    ];
    const elements = messages.map((m) => el(m.id));
    const runs = groupMessageElements(messages, elements);
    const boxes = runs.filter((r) => r.kind === "subagent");
    expect(boxes).toHaveLength(1);
    expect(boxes[0].kind === "subagent" && boxes[0].agentId).toBe(
      "Pipeline · 3 nodes",
    );
  });

  it("boxes a spawn_registered_graph run labeled by graph_id", () => {
    const messages = [
      asst("regspawn", {
        spawnTool: "spawn_registered_graph",
        spawnArgs: { graph_id: "rt-sast-scan" },
        tcid: "R1",
      }),
      asst("swarm-node", { text: "node prose" }),
      toolResult("r-reg", "R1"),
    ];
    const elements = messages.map((m) => el(m.id));
    const runs = groupMessageElements(messages, elements);
    const boxes = runs.filter((r) => r.kind === "subagent");
    expect(boxes).toHaveLength(1);
    expect(boxes[0].kind === "subagent" && boxes[0].agentId).toBe(
      "Pipeline · rt-sast-scan",
    );
  });

  it("does NOT box spawn_subagent_async (separate live-window surface)", () => {
    const messages = [
      asst("asyncspawn", {
        spawnTool: "spawn_subagent_async",
        spawnArgs: { agent_id: "eval-runner" },
        tcid: "A1",
      }),
    ];
    const elements = messages.map((m) => el(m.id));
    const runs = groupMessageElements(messages, elements);
    expect(runs.every((r) => r.kind === "coordinator")).toBe(true);
  });
});
