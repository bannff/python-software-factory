/**
 * CopilotKit v2 `useComponent` canary (bd:python-factory-deep / EPIC
 * python-factory-iet5 bd-B). Pins the under-the-hood routing flagged
 * in the strands-expert verdict (mem 87e4611d, sections L2/L8) and
 * the four-carrier model in `.agents/steering/a2ui-protocol.md`.
 *
 * Contract pinned:
 *   - `useComponent` is sugar over `useFrontendTool`
 *     (`@copilotkitnext/[email protected]/dist/hooks/use-component.mjs:55-66`)
 *     — a typed render closure is wrapped on the FE-tool's
 *     `render: ({ args }) => <Component {...args} />` slot.
 *   - The LLM activates a typed component by emitting a normal tool
 *     call with the registered name. CopilotKit's render layer
 *     (`@copilotkitnext/[email protected]/dist/hooks/use-render-tool-call.mjs:54-75`)
 *     reads the FE-tool registry, partial-parses the streamed args,
 *     and mounts the typed render component.
 *
 * If a future upgrade switches `useComponent` off `useFrontendTool`,
 * or reshapes the `renderToolCalls` registry contract, these tests
 * fail fast.
 */

import { describe, expect, it, vi } from "vitest";
import { act, render, waitFor } from "@testing-library/react";
import * as React from "react";
import { Observable } from "rxjs";
import { z } from "zod";
import {
  CopilotKitProvider,
  useCopilotKit,
  useComponent,
} from "@copilotkit/react-core/v2";
import { useRenderToolCall } from "@copilotkit/react-core/v2";
import {
  AbstractAgent,
  EventType,
  type BaseEvent,
  type RunAgentInput,
} from "@ag-ui/client";

const COMPONENT_NAME = "canary_card";
const TOOL_CALL_ID = "tc-canary-uc-1";
const RUN_ID = "run-canary-uc-1";
const ENTITY_ID = "sandbox-bg-007";
const ARG_PAYLOAD = JSON.stringify({ entity_id: ENTITY_ID, depth: 1 });

const CanaryArgs = z.object({
  entity_id: z.string(),
  depth: z.number().optional(),
});

type CanaryProps = z.infer<typeof CanaryArgs>;

class ScriptedAgent extends AbstractAgent {
  public runCallCount = 0;
  private readonly events: BaseEvent[];

  constructor(events: BaseEvent[]) {
    super({ agentId: "default", threadId: "thread-canary-uc" });
    this.events = events;
  }

  run(_input: RunAgentInput): Observable<BaseEvent> {
    this.runCallCount += 1;
    return new Observable<BaseEvent>((subscriber) => {
      for (const event of this.events) subscriber.next(event);
      subscriber.complete();
    });
  }
}

function makeComponentCallEvents(): BaseEvent[] {
  return [
    { type: EventType.RUN_STARTED, threadId: "thread-canary-uc", runId: RUN_ID },
    {
      type: EventType.TOOL_CALL_START,
      toolCallId: TOOL_CALL_ID,
      toolCallName: COMPONENT_NAME,
      parentMessageId: "asst-canary-uc-1",
    } as BaseEvent,
    {
      type: EventType.TOOL_CALL_ARGS,
      toolCallId: TOOL_CALL_ID,
      delta: ARG_PAYLOAD,
    } as BaseEvent,
    { type: EventType.TOOL_CALL_END, toolCallId: TOOL_CALL_ID } as BaseEvent,
    { type: EventType.RUN_FINISHED, threadId: "thread-canary-uc", runId: RUN_ID } as BaseEvent,
  ];
}

interface AssistantToolCall {
  id: string;
  type: "function";
  function: { name: string; arguments: string };
}

interface RunnerHandle {
  drive: () => Promise<void>;
  renderCall: (toolCall: AssistantToolCall) => React.ReactNode;
}

interface HarnessProps {
  agent: AbstractAgent;
  renderSpy: (props: CanaryProps) => void;
  onReady: (handle: RunnerHandle) => void;
}

function Harness({ agent, renderSpy, onReady }: HarnessProps) {
  useComponent({
    name: COMPONENT_NAME,
    description: "Canary typed card — pins useComponent dispatcher contract.",
    parameters: CanaryArgs,
    render: (props: CanaryProps) => {
      renderSpy(props);
      return <div data-testid="canary-card">{props.entity_id}</div>;
    },
  });
  const { copilotkit } = useCopilotKit();
  const renderToolCall = useRenderToolCall();
  React.useEffect(() => {
    onReady({
      drive: async () => {
        await copilotkit.runAgent({ agent });
      },
      renderCall: (toolCall) =>
        renderToolCall({ toolCall, toolMessage: undefined }) ?? null,
    });
  }, [agent, copilotkit, renderToolCall, onReady]);
  return null;
}

function Slot({ node }: { node: React.ReactNode }) {
  return <div data-testid="render-slot">{node}</div>;
}

async function runCanary(agent: ScriptedAgent, renderSpy: HarnessProps["renderSpy"]) {
  let handle: RunnerHandle | undefined;
  const { rerender } = render(
    <CopilotKitProvider selfManagedAgents={{ default: agent }}>
      <Harness agent={agent} renderSpy={renderSpy} onReady={(h) => (handle = h)} />
    </CopilotKitProvider>,
  );
  await waitFor(() => expect(handle).toBeDefined());
  await act(async () => {
    await handle!.drive();
  });
  // After the run, materialise the assistant tool call from the agent's
  // message buffer — this is what the chat surface does.
  const assistantToolCalls: AssistantToolCall[] = [];
  for (const m of agent.messages) {
    const calls = (m as { toolCalls?: Array<Partial<AssistantToolCall>> }).toolCalls;
    if (!calls) continue;
    for (const tc of calls) {
      if (!tc.id || !tc.function) continue;
      assistantToolCalls.push({
        id: tc.id,
        type: "function",
        function: tc.function,
      });
    }
  }
  const target = assistantToolCalls.find((tc) => tc.id === TOOL_CALL_ID);
  expect(target, "agent.messages should expose the assistant tool call").toBeDefined();
  const node = handle!.renderCall(target!);
  rerender(
    <CopilotKitProvider selfManagedAgents={{ default: agent }}>
      <Harness agent={agent} renderSpy={renderSpy} onReady={() => {}} />
      <Slot node={node} />
    </CopilotKitProvider>,
  );
  return { agent, assistantToolCalls };
}

describe("CopilotKit v2 useComponent canary (bd:python-factory-deep)", () => {
  it("renders the typed component when the LLM emits a tool call with the registered name", async () => {
    const agent = new ScriptedAgent(makeComponentCallEvents());
    const renderSpy = vi.fn<(props: CanaryProps) => void>();

    await runCanary(agent, renderSpy);

    await waitFor(() => expect(renderSpy).toHaveBeenCalled());
    const lastProps = renderSpy.mock.calls[renderSpy.mock.calls.length - 1]?.[0];
    expect(lastProps).toEqual({ entity_id: ENTITY_ID, depth: 1 });
  });

  it("parses Zod-shaped args verbatim from the AG-UI TOOL_CALL_ARGS payload", async () => {
    const agent = new ScriptedAgent(makeComponentCallEvents());
    const renderSpy = vi.fn<(props: CanaryProps) => void>();

    await runCanary(agent, renderSpy);

    await waitFor(() => expect(renderSpy).toHaveBeenCalled());
    const observed = renderSpy.mock.calls[renderSpy.mock.calls.length - 1]?.[0];
    const expected = JSON.parse(ARG_PAYLOAD) as CanaryProps;
    expect(observed?.entity_id).toBe(expected.entity_id);
    expect(observed?.depth).toBe(expected.depth);
    // The agent runs once for the initial turn; CopilotKit re-runs the
    // agent because `useComponent` wraps `useFrontendTool` and the
    // synthesised handler returns void, which the dispatcher treats as
    // a follow-up. ≥1 here is the loose pin — pinned to exactly 2 in
    // the dispatcher canary.
    expect(agent.runCallCount).toBeGreaterThanOrEqual(1);
  });
});
