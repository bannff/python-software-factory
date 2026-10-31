import { describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen } from "@testing-library/react";
import { Observable } from "rxjs";
import { CopilotKitProvider } from "@copilotkit/react-core/v2";
import { AbstractAgent, type BaseEvent, type RunAgentInput } from "@ag-ui/client";
import { makeAssistantMessageSlot } from "../feedback-message-slot";

const MESSAGE = { id: "msg-1", role: "assistant" as const, content: "Hello there" };

class IdleAgent extends AbstractAgent {
  constructor() { super({ agentId: "default", threadId: "thread-a" }); }
  run(_input: RunAgentInput): Observable<BaseEvent> {
    return new Observable<BaseEvent>((s) => s.complete());
  }
}

function renderSlot(callbacks: Parameters<typeof makeAssistantMessageSlot>[0]) {
  const Slot = makeAssistantMessageSlot(callbacks);
  return render(
    <CopilotKitProvider selfManagedAgents={{ default: new IdleAgent() }}>
      <Slot message={MESSAGE} />
    </CopilotKitProvider>,
  );
}

describe("makeAssistantMessageSlot — onPin (row 9, feature-map)", () => {
  it("renders a Pin toolbar button and fires the callback with the message", () => {
    const onPin = vi.fn();
    renderSlot({ onPin });
    fireEvent.click(screen.getByRole("button", { name: "Pin this message" }));
    expect(onPin).toHaveBeenCalledWith(MESSAGE);
  });

  it("omits the Pin button entirely when no callback is supplied", () => {
    renderSlot({ onRewind: vi.fn() });
    expect(screen.queryByRole("button", { name: "Pin this message" })).toBeNull();
  });

  it("renders Rewind and Pin side by side when both callbacks are supplied", () => {
    renderSlot({ onRewind: vi.fn(), onPin: vi.fn() });
    expect(screen.getByRole("button", { name: "Rewind to this point" })).toBeTruthy();
    expect(screen.getByRole("button", { name: "Pin this message" })).toBeTruthy();
  });
});
