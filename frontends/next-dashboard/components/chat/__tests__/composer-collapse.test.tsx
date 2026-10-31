import { describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen } from "@testing-library/react";
import { Observable } from "rxjs";
import { CopilotKitProvider } from "@copilotkit/react-core/v2";
import { AbstractAgent, type BaseEvent, type RunAgentInput } from "@ag-ui/client";
import { makeCollapsibleComposerInput } from "../composer-collapse";

class IdleAgent extends AbstractAgent {
  constructor() { super({ agentId: "default", threadId: "thread-a" }); }
  run(_input: RunAgentInput): Observable<BaseEvent> {
    return new Observable<BaseEvent>((s) => s.complete());
  }
}

function renderInput(enabled: boolean, value = "") {
  const Input = makeCollapsibleComposerInput(enabled, {});
  return render(
    <CopilotKitProvider selfManagedAgents={{ default: new IdleAgent() }}>
      <Input value={value} onChange={vi.fn()} />
    </CopilotKitProvider>,
  );
}

describe("makeCollapsibleComposerInput (row 12, feature-map)", () => {
  it("renders the plain composer with no collapse button when the preference is off", () => {
    renderInput(false);
    expect(screen.queryByRole("button", { name: "Collapse the message input" })).toBeNull();
  });

  it("renders a Collapse button when the preference is on, and collapsing shows a restore bar", () => {
    renderInput(true, "hello there\nsecond line");
    const collapseButton = screen.getByRole("button", { name: "Collapse the message input" });
    fireEvent.click(collapseButton);
    const restoreBar = screen.getByRole("button", { name: "Restore the message input" });
    expect(restoreBar.textContent).toContain("hello there");
    expect(restoreBar.textContent).not.toContain("second line");
  });

  it("shows a truthful 'Empty draft' label instead of a blank restore bar", () => {
    renderInput(true, "");
    fireEvent.click(screen.getByRole("button", { name: "Collapse the message input" }));
    expect(screen.getByRole("button", { name: "Restore the message input" }).textContent)
      .toContain("Empty draft");
  });

  it("restores the composer on click, dropping the restore bar", () => {
    renderInput(true, "draft");
    fireEvent.click(screen.getByRole("button", { name: "Collapse the message input" }));
    fireEvent.click(screen.getByRole("button", { name: "Restore the message input" }));
    expect(screen.getByRole("button", { name: "Collapse the message input" })).toBeTruthy();
    expect(screen.queryByRole("button", { name: "Restore the message input" })).toBeNull();
  });
});
