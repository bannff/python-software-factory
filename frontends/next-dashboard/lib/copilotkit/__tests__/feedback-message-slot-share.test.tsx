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

describe("makeAssistantMessageSlot — onShare (row 13, feature-map)", () => {
  it("renders a Share toolbar button and fires the callback with the message", () => {
    const onShare = vi.fn();
    renderSlot({ onShare });
    fireEvent.click(screen.getByRole("button", { name: "Share as image" }));
    expect(onShare).toHaveBeenCalledWith(MESSAGE);
  });

  it("omits the Share button when no callback is supplied", () => {
    renderSlot({ onPin: vi.fn() });
    expect(screen.queryByRole("button", { name: "Share as image" })).toBeNull();
  });
});
