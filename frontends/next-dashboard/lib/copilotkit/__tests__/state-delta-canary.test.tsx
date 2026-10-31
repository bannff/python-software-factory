/**
 * STATE_SNAPSHOT / STATE_DELTA canary (bd-pws3, EPIC python-factory-iet5).
 *
 * Pins carrier #2 of the four-carrier model
 * (.agents/steering/a2ui-protocol.md) at the dispatcher edge: when a
 * Strands chat agent emits an AG-UI STATE_SNAPSHOT or STATE_DELTA
 * event, `agent.state.canvas.<slot>` MUST mutate the same way the
 * production dashboard sees it after `useAgent` re-renders.
 *
 * Mirrors `dispatcher-canary.test.tsx`. Dispatcher source pins:
 *   - STATE_SNAPSHOT consumer: `defaultApplyEvents` in
 *     `@ag-ui/[email protected]/dist/index.mjs` — `case i.STATE_SNAPSHOT`
 *     replaces the agent's state object verbatim with `event.snapshot`.
 *   - STATE_DELTA consumer: same module, `case i.STATE_DELTA`, calls
 *     `fast-json-patch.applyPatch(state, delta, validate=true,
 *     mutate=false)` — RFC 6902 with strict validation, no in-place
 *     mutation.
 *   - StateManager keying: `@copilotkitnext/[email protected]/dist/index.mjs`
 *     L1124-1290 keys state by `(agentId, threadId, runId)`.
 *
 * Verdicts: `2dabeff1-eee0-47cc-9d98-1165ebc88e96` (meta-architect Q2,
 * Q9, Q10) and `87e4611d-843d-47d0-9732-bdabbab7d4e9` (strands-expert
 * L3, L4).
 */

import { describe, expect, it } from "vitest";
import { act, render, waitFor } from "@testing-library/react";
import * as React from "react";
import { Observable } from "rxjs";
import {
  CopilotKitProvider,
  useCopilotKit,
} from "@copilotkit/react-core/v2";
import {
  AbstractAgent,
  EventType,
  type BaseEvent,
  type RunAgentInput,
} from "@ag-ui/client";

const RUN_ID = "run-state-canary-1";
const THREAD = "thread-state-canary";

const GRAPH_PAYLOAD = {
  components: [
    { id: "n1", type: "graph_node", props: { label: "Alpha" } },
    { id: "n2", type: "graph_node", props: { label: "Beta" } },
  ],
  name: "graph",
};

class ScriptedAgent extends AbstractAgent {
  public runCallCount = 0;
  private readonly events: BaseEvent[];

  constructor(events: BaseEvent[]) {
    super({ agentId: "default", threadId: THREAD });
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

interface HarnessProps {
  agent: AbstractAgent;
  onReady: (runner: () => Promise<void>) => void;
}

function Harness({ agent, onReady }: HarnessProps) {
  const { copilotkit } = useCopilotKit();
  React.useEffect(() => {
    onReady(async () => {
      await copilotkit.runAgent({ agent });
    });
  }, [agent, copilotkit, onReady]);
  return null;
}

async function runCanary(agent: ScriptedAgent) {
  let runner: (() => Promise<void>) | undefined;
  render(
    <CopilotKitProvider selfManagedAgents={{ default: agent }}>
      <Harness agent={agent} onReady={(r) => (runner = r)} />
    </CopilotKitProvider>,
  );
  await waitFor(() => expect(runner).toBeDefined());
  await act(async () => {
    await runner!();
  });
}

describe("STATE_SNAPSHOT / STATE_DELTA canary (bd-pws3)", () => {
  it("STATE_SNAPSHOT seeds agent.state.canvas with the full payload", async () => {
    const events: BaseEvent[] = [
      { type: EventType.RUN_STARTED, threadId: THREAD, runId: RUN_ID },
      {
        type: EventType.STATE_SNAPSHOT,
        snapshot: { canvas: { graph: GRAPH_PAYLOAD } },
      } as BaseEvent,
      { type: EventType.RUN_FINISHED, threadId: THREAD, runId: RUN_ID } as BaseEvent,
    ];
    const agent = new ScriptedAgent(events);

    await runCanary(agent);

    const state = agent.state as { canvas?: { graph?: typeof GRAPH_PAYLOAD } };
    expect(state.canvas).toBeDefined();
    expect(state.canvas?.graph).toEqual(GRAPH_PAYLOAD);
    expect(state.canvas?.graph?.components).toHaveLength(2);
  });

  it("STATE_DELTA replace op overwrites /canvas/graph after a snapshot seed", async () => {
    // Mirror the production mapper flow (bd-D, see
    // `ag_ui_mapper_chat_state.on_state_delta`): the first paint of a
    // run emits STATE_SNAPSHOT carrying the full slot value, then
    // subsequent paints emit STATE_DELTA with a `replace` op. This
    // satisfies fast-json-patch's strict-validation contract — `replace`
    // requires the target path to already exist; the mapper's
    // SNAPSHOT-first discipline keeps `add` off the wire.
    const initialPayload = { ...GRAPH_PAYLOAD, name: "initial" };
    const events: BaseEvent[] = [
      { type: EventType.RUN_STARTED, threadId: THREAD, runId: RUN_ID },
      {
        type: EventType.STATE_SNAPSHOT,
        snapshot: { canvas: { graph: initialPayload } },
      } as BaseEvent,
      {
        type: EventType.STATE_DELTA,
        delta: [
          { op: "replace", path: "/canvas/graph", value: GRAPH_PAYLOAD },
        ],
      } as BaseEvent,
      { type: EventType.RUN_FINISHED, threadId: THREAD, runId: RUN_ID } as BaseEvent,
    ];
    const agent = new ScriptedAgent(events);

    await runCanary(agent);

    const state = agent.state as { canvas?: { graph?: typeof GRAPH_PAYLOAD } };
    expect(state.canvas?.graph).toEqual(GRAPH_PAYLOAD);
    expect(state.canvas?.graph?.name).toBe("graph");
    // Patch overwrote the snapshot value (initial→graph).
    expect(state.canvas?.graph?.name).not.toBe("initial");
  });

  it("STATE_DELTA on missing parent fails validation and leaves state unchanged", async () => {
    // Pin meta-architect Q10(2) concern: JSON-Patch validation MUST
    // catch a `replace` (or `add`) on a missing parent and the
    // dispatcher MUST NOT silently mutate state. The dispatcher logs
    // a `console.warn("Failed to apply state patch")` but the
    // `state` object stays as the prior snapshot.
    const events: BaseEvent[] = [
      { type: EventType.RUN_STARTED, threadId: THREAD, runId: RUN_ID },
      {
        type: EventType.STATE_SNAPSHOT,
        snapshot: { canvas: {} },
      } as BaseEvent,
      {
        type: EventType.STATE_DELTA,
        // /missing/parent doesn't exist — fast-json-patch with
        // validate=true raises and the dispatcher swallows.
        delta: [
          { op: "replace", path: "/missing/parent/leaf", value: 42 },
        ],
      } as BaseEvent,
      { type: EventType.RUN_FINISHED, threadId: THREAD, runId: RUN_ID } as BaseEvent,
    ];
    const agent = new ScriptedAgent(events);

    await runCanary(agent);

    const state = agent.state as Record<string, unknown>;
    // canvas seed survives; missing patch did not silently slip in.
    expect(state.canvas).toEqual({});
    expect("missing" in state).toBe(false);
  });
});
