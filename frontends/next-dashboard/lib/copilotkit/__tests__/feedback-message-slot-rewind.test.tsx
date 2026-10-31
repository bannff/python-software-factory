import { describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen } from "@testing-library/react";
import { Observable } from "rxjs";
import { CopilotKitProvider } from "@copilotkit/react-core/v2";
import { AbstractAgent, type BaseEvent, type RunAgentInput } from "@ag-ui/client";
import type { AssistantMessage } from "@ag-ui/core";
import { makeAssistantMessageSlot } from "../feedback-message-slot";

const MESSAGE = { id: "msg-1", role: "assistant" as const, content: "Hello there" };

class IdleAgent extends AbstractAgent {
  constructor() { super({ agentId: "default", threadId: "thread-a" }); }
  run(_input: RunAgentInput): Observable<BaseEvent> {
    return new Observable<BaseEvent>((s) => s.complete());
  }
}

function renderSlot(onRewind?: (m: AssistantMessage) => void) {
  const Slot = makeAssistantMessageSlot({ onRewind });
  return render(
    <CopilotKitProvider selfManagedAgents={{ default: new IdleAgent() }}>
      <Slot message={MESSAGE} />
    </CopilotKitProvider>,
  );
}

describe("makeAssistantMessageSlot — onRewind (row 15, feature-map)", () => {
  it("renders a Rewind toolbar button and fires the callback with the message", () => {
    const onRewind = vi.fn();
    renderSlot(onRewind);
    fireEvent.click(screen.getByRole("button", { name: "Rewind to this point" }));
    expect(onRewind).toHaveBeenCalledWith(MESSAGE);
  });

  it("omits the Rewind button entirely when no callback is supplied", () => {
    renderSlot(undefined);
    expect(screen.queryByRole("button", { name: "Rewind to this point" })).toBeNull();
  });
});
