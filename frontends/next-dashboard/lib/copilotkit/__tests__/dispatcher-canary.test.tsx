/**
 * CopilotKit v2 dispatcher canary (bd-f2h9 / regression pin for bd-115z).
 *
 * Renders a real `<CopilotKitProvider>` from `@copilotkitnext/react`,
 * registers a `useFrontendTool` with a spy handler, and drives a
 * minimal AG-UI `AbstractAgent` through canonical event sequences. The
 * provider talks to the actual installed `@copilotkitnext/core` /
 * `@ag-ui/client`, so a future upgrade that refactors
 * `processAgentResult` or `defaultApplyEvents` will trip these tests.
 *
 * Two cases pin the contract revealed by the strands-expert /
 * meta-architect verdicts:
 *   1. TOOL_CALL_END *without* TOOL_CALL_RESULT → handler runs, tool
 *      reply synthesised, `needsFollowUp` re-runs the agent.
 *   2. TOOL_CALL_END *with* TOOL_CALL_RESULT → handler is skipped (the
 *      bd-115z bug shape). Test 2 is the actual regression pin.
 */

import { describe, expect, it, vi } from "vitest";
import { act, render, waitFor } from "@testing-library/react";
import * as React from "react";
import { Observable } from "rxjs";
import { z } from "zod";
import {
  CopilotKitProvider,
  useCopilotKit,
  useFrontendTool,
} from "@copilotkit/react-core/v2";
import {
  AbstractAgent,
  EventType,
  type BaseEvent,
  type RunAgentInput,
} from "@ag-ui/client";

const NavigateArgs = z.object({ view: z.string() });
const TOOL_CALL_ID = "tc-graph-1";
const RUN_ID = "run-canary-1";
const ARG_PAYLOAD = '{"view":"graph"}';

class ScriptedAgent extends AbstractAgent {
  public runCallCount = 0;
  private readonly firstTurnEvents: BaseEvent[];
  private readonly resumeTurnEvents: BaseEvent[];

  constructor(firstTurn: BaseEvent[], resumeTurn: BaseEvent[]) {
    super({ agentId: "default", threadId: "thread-canary" });
    this.firstTurnEvents = firstTurn;
    this.resumeTurnEvents = resumeTurn;
  }

  run(_input: RunAgentInput): Observable<BaseEvent> {
    this.runCallCount += 1;
    const events =
      this.runCallCount === 1 ? this.firstTurnEvents : this.resumeTurnEvents;
    return new Observable<BaseEvent>((subscriber) => {
      for (const event of events) subscriber.next(event);
      subscriber.complete();
    });
  }
}

function makeFeToolCallEvents(includeResult: boolean): BaseEvent[] {
  const base: BaseEvent[] = [
    { type: EventType.RUN_STARTED, threadId: "thread-canary", runId: RUN_ID },
    {
      type: EventType.TOOL_CALL_START,
      toolCallId: TOOL_CALL_ID,
      toolCallName: "fe_navigate_canvas",
      parentMessageId: "asst-canary-1",
    } as BaseEvent,
    {
      type: EventType.TOOL_CALL_ARGS,
      toolCallId: TOOL_CALL_ID,
      delta: ARG_PAYLOAD,
    } as BaseEvent,
    { type: EventType.TOOL_CALL_END, toolCallId: TOOL_CALL_ID } as BaseEvent,
  ];
  if (includeResult) {
    base.push({
      type: EventType.TOOL_CALL_RESULT,
      messageId: "tool-msg-server-canary",
      toolCallId: TOOL_CALL_ID,
      content: '{"_frontend_pending":true}',
      role: "tool",
    } as BaseEvent);
  }
  base.push({ type: EventType.RUN_FINISHED, threadId: "thread-canary", runId: RUN_ID } as BaseEvent);
  return base;
}

const RESUME_EVENTS: BaseEvent[] = [
  { type: EventType.RUN_STARTED, threadId: "thread-canary", runId: "run-canary-2" },
  { type: EventType.RUN_FINISHED, threadId: "thread-canary", runId: "run-canary-2" } as BaseEvent,
];

interface HarnessProps {
  agent: AbstractAgent;
  spy: (args: { view: string }) => Promise<{ success: true; view: string }>;
  onReady: (runner: () => Promise<void>) => void;
}

function Harness({ agent, spy, onReady }: HarnessProps) {
  useFrontendTool({
    name: "fe_navigate_canvas",
    description: "switch canvas",
    parameters: NavigateArgs,
    handler: spy,
  });
  const { copilotkit } = useCopilotKit();
  React.useEffect(() => {
    onReady(async () => {
      await copilotkit.runAgent({ agent });
    });
  }, [agent, copilotkit, onReady]);
  return null;
}

async function runCanary(agent: ScriptedAgent, spy: HarnessProps["spy"]) {
  let runner: (() => Promise<void>) | undefined;
  render(
    <CopilotKitProvider selfManagedAgents={{ default: agent }}>
      <Harness agent={agent} spy={spy} onReady={(r) => (runner = r)} />
    </CopilotKitProvider>,
  );
  await waitFor(() => expect(runner).toBeDefined());
  await act(async () => {
    await runner!();
  });
}

/* ── Human-fired actions share the transcript (bd:python-factory-3jcls.7) ──
 *
 * ANTI-DRIFT CONDITION 4. A human firing a tool from a view must land in the
 * SAME message list, in the SAME shape, as the agent streaming the same tool
 * — otherwise the human path and the agent path drift into two products.
 *
 * Asserted against the INSTALLED SDK, not an assumption of it: the fixture
 * drives the real `AbstractAgent.addMessages`
 * (`@ag-ui/client/dist/index.d.ts:435`) and compares the resulting messages
 * field-for-field against what `defaultApplyEvents` produces from a streamed
 * TOOL_CALL_* sequence. If an upgrade changes either shape, this trips.
 */
function humanFiredMessages(toolCallId: string) {
  const args = JSON.stringify({ key: "k" });
  return [
    {
      id: `human-action-${toolCallId}`,
      role: "assistant" as const,
      toolCalls: [
        { id: toolCallId, type: "function" as const,
          function: { name: "cache_get", arguments: args } },
      ],
    },
    {
      id: `human-action-result-${toolCallId}`,
      role: "tool" as const,
      toolCallId,
      content: JSON.stringify({ found: true }),
    },
  ];
}

describe("human-fired action transcript parity (bd:python-factory-3jcls.7)", () => {
  it("addMessages-injected tool messages match the streamed shape", async () => {
    // (a) The agent path: drive a real TOOL_CALL_* stream through the SDK.
    const streamed = new ScriptedAgent(makeFeToolCallEvents(true), RESUME_EVENTS);
    await runCanary(streamed, vi.fn(async ({ view }: { view: string }) => ({
      success: true as const, view,
    })));
    const streamedAssistant = streamed.messages.find(
      (m) => m.role === "assistant" && (m as { toolCalls?: unknown[] }).toolCalls?.length,
    ) as { toolCalls: { id: string; type: string; function: { name: string; arguments: string } }[] };
    const streamedTool = streamed.messages.find((m) => m.role === "tool") as {
      role: string; toolCallId: string; content: string;
    };

    // (b) The human path: inject via the installed addMessages.
    const human = new ScriptedAgent([], RESUME_EVENTS);
    const humanTcId = "human-gesture-1";
    act(() => { human.addMessage(humanFiredMessages(humanTcId)[0] as never); });
    act(() => { human.addMessages([humanFiredMessages(humanTcId)[1]] as never); });

    const humanAssistant = human.messages.find(
      (m) => m.role === "assistant",
    ) as typeof streamedAssistant;
    const humanTool = human.messages.find((m) => m.role === "tool") as typeof streamedTool;

    // Same field set on both paths — the whole point of one transcript.
    expect(Object.keys(humanAssistant.toolCalls[0]).sort())
      .toEqual(Object.keys(streamedAssistant.toolCalls[0]).sort());
    expect(Object.keys(humanAssistant.toolCalls[0].function).sort())
      .toEqual(Object.keys(streamedAssistant.toolCalls[0].function).sort());
    expect(humanAssistant.toolCalls[0].type).toBe(streamedAssistant.toolCalls[0].type);
    expect(typeof humanAssistant.toolCalls[0].function.arguments)
      .toBe(typeof streamedAssistant.toolCalls[0].function.arguments);

    expect(humanTool.role).toBe(streamedTool.role);
    expect(humanTool.toolCallId).toBe(humanTcId);
    expect(typeof humanTool.content).toBe(typeof streamedTool.content);
  });

  it("injected messages ride the next run body so the agent sees them", async () => {
    const agent = new ScriptedAgent(RESUME_EVENTS, RESUME_EVENTS);
    const seen: RunAgentInput[] = [];
    const originalRun = agent.run.bind(agent);
    agent.run = (input: RunAgentInput) => { seen.push(input); return originalRun(input); };

    const tcId = "human-gesture-2";
    act(() => { agent.addMessages(humanFiredMessages(tcId) as never); });
    await act(async () => { await agent.runAgent(); });

    expect(seen).toHaveLength(1);
    const ids = seen[0].messages.map((m) => m.id);
    expect(ids).toContain(`human-action-${tcId}`);
    expect(ids).toContain(`human-action-result-${tcId}`);
  });
});

describe("CopilotKit v2 dispatcher canary (bd-f2h9)", () => {
  it("dispatches FE handler when TOOL_CALL_END arrives without TOOL_CALL_RESULT", async () => {
    const agent = new ScriptedAgent(makeFeToolCallEvents(false), RESUME_EVENTS);
    const spy = vi.fn(async ({ view }: { view: string }) => ({
      success: true as const,
      view,
    }));

    await runCanary(agent, spy);

    expect(spy).toHaveBeenCalledTimes(1);
    expect(spy.mock.calls[0]?.[0]).toEqual({ view: "graph" });
    const toolReplies = agent.messages.filter(
      (m) => m.role === "tool" && (m as { toolCallId?: string }).toolCallId === TOOL_CALL_ID,
    );
    expect(toolReplies).toHaveLength(1);
    expect(toolReplies[0].content).toContain('"view":"graph"');
    expect(agent.runCallCount).toBe(2);
  });

  it("skips FE handler when backend also emits TOOL_CALL_RESULT (bd-115z bug shape)", async () => {
    const agent = new ScriptedAgent(makeFeToolCallEvents(true), RESUME_EVENTS);
    const spy = vi.fn(async ({ view }: { view: string }) => ({
      success: true as const,
      view,
    }));

    await runCanary(agent, spy);

    expect(spy).not.toHaveBeenCalled();
    const toolReplies = agent.messages.filter(
      (m) => m.role === "tool" && (m as { toolCallId?: string }).toolCallId === TOOL_CALL_ID,
    );
    expect(toolReplies).toHaveLength(1);
    expect(toolReplies[0].content).toContain("_frontend_pending");
    expect(agent.runCallCount).toBe(1);
  });
});
