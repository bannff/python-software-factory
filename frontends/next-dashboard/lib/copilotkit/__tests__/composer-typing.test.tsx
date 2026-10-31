/**
 * Composer typing regression (P1 owner report 2026-09-15: "hi you there" typed
 * backwards). Renders the REAL v2 `<CopilotChat>` — not a mocked input — so
 * the slot passes through `CopilotChat`'s `ts-deepmerge` of props. A
 * `forwardRef` slot is an object and gets cloned into a new component type per
 * render, remounting the textarea on every keystroke. A plain function slot is
 * preserved by the merge. This test guards that contract.
 */
import { describe, expect, it, vi } from "vitest";
import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { Observable } from "rxjs";
import { CopilotChat, CopilotKitProvider } from "@copilotkit/react-core/v2";
import { AbstractAgent, type BaseEvent, type RunAgentInput } from "@ag-ui/client";

vi.mock("@/lib/hooks/use-mcp-connection", () => ({
  useMcpConnection: () => ({ status: "connected", ready: true, retry: vi.fn() }),
}));

import { McpReadyTextArea } from "../mcp-connection-gate";

class IdleAgent extends AbstractAgent {
  constructor() { super({ agentId: "default", threadId: "thread-typing" }); }
  run(_input: RunAgentInput): Observable<BaseEvent> {
    return new Observable<BaseEvent>((s) => s.complete());
  }
}

const TEXTAREA = "copilot-chat-textarea";

function typeChar(ch: string) {
  const node = screen.getByTestId(TEXTAREA) as HTMLTextAreaElement;
  const pos = node.selectionStart ?? node.value.length;
  const next = node.value.slice(0, pos) + ch + node.value.slice(pos);
  act(() => { fireEvent.change(node, { target: { value: next } }); });
  const after = screen.getByTestId(TEXTAREA) as HTMLTextAreaElement;
  after.setSelectionRange(pos + 1, pos + 1);
  return after;
}

describe("chat composer keeps one textarea across keystrokes", () => {
  it("is a plain function slot that ts-deepmerge preserves by reference", () => {
    // forwardRef/memo return objects; ts-deepmerge clones objects, not functions.
    expect(typeof McpReadyTextArea).toBe("function");
  });

  it("types ten characters in order through the real CopilotChat surface", async () => {
    const agent = new IdleAgent();
    render(
      <CopilotKitProvider selfManagedAgents={{ default: agent }}>
        <CopilotChat agentId="default" input={{ textArea: McpReadyTextArea }} />
      </CopilotKitProvider>,
    );
    await waitFor(() => expect(screen.getByTestId(TEXTAREA)).toBeDefined());
    const first = screen.getByTestId(TEXTAREA) as HTMLTextAreaElement;
    first.focus();
    let last = first;
    for (const ch of "hi you the") {
      last = typeChar(ch);
      expect(last).toBe(first);
    }
    expect(last.value).toBe("hi you the");
    expect(last.disabled).toBe(false);
  });
});
