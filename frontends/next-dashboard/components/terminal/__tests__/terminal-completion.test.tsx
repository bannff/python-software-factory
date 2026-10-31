import { act, cleanup, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { Terminal } from "@xterm/xterm";

const mocks = vi.hoisted(() => ({ complete: vi.fn() }));
vi.mock("@/lib/terminal-api", () => ({
  completeTerminalSession: (...args: unknown[]) => mocks.complete(...args),
}));
import { TerminalCompletion } from "../terminal-completion";

class FakeTerminal {
  line = "$ cd doc";
  cursor = this.line.length;
  cursorListener = () => {};
  lineListener = () => {};
  keyHandler: (event: KeyboardEvent) => boolean = () => true;
  textarea = document.createElement("textarea");
  element = document.createElement("div");
  cols = 80;
  rows = 24;
  parser = { registerOscHandler: () => ({ dispose: vi.fn() }) };
  buffer = { active: {
    type: "normal", baseY: 0, cursorY: 0,
    get cursorX() { return owner.cursor; },
    getLine: () => ({
      isWrapped: false, length: this.line.length,
      getCell: (index: number) => ({ getWidth: () => 1, getChars: () => this.line[index] ?? "" }),
      translateToString: () => this.line,
    }),
  }};
  onCursorMove(listener: () => void) { this.cursorListener = listener; return { dispose: vi.fn() }; }
  onLineFeed(listener: () => void) { this.lineListener = listener; return { dispose: vi.fn() }; }
  attachCustomKeyEventHandler(handler: (event: KeyboardEvent) => boolean) { this.keyHandler = handler; }
  fireCursor() { this.cursorListener(); }
  key(key: string, extra: Partial<KeyboardEvent> = {}) {
    const event = {
      type: "keydown", key, code: key, keyCode: 0,
      ctrlKey: false, metaKey: false, altKey: false, shiftKey: false,
      isComposing: false, preventDefault: vi.fn(), stopPropagation: vi.fn(), ...extra,
    } as unknown as KeyboardEvent;
    return { passed: this.keyHandler(event), event };
  }
}
let owner: FakeTerminal;
const entry = (name: string, dir = true) => ({
  name, dir, at: 0, kind: null, description: null, nospace: false,
});

async function open(
  entries = [entry("docs"), entry("doctor")],
  response: Partial<{ directory: string | null; prefix: string; truncated: boolean }> = {},
) {
  owner = new FakeTerminal();
  mocks.complete.mockResolvedValue({
    directory: "/work", prefix: "doc", entries, truncated: false, ...response,
  });
  const send = vi.fn();
  render(<TerminalCompletion term={owner as unknown as Terminal} sessionId={`term_${"a".repeat(32)}`}
    active enabled send={send} />);
  act(() => owner.fireCursor());
  await screen.findByRole("listbox", { name: "Terminal completions" });
  return send;
}

beforeEach(() => { mocks.complete.mockReset(); });
afterEach(cleanup);

describe("TerminalCompletion", () => {
  it("stays dormant when the saved preference disables it", async () => {
    owner = new FakeTerminal();
    render(<TerminalCompletion term={owner as unknown as Terminal} sessionId={`term_${"a".repeat(32)}`}
      active enabled={false} send={vi.fn()} />);
    act(() => owner.fireCursor());
    await new Promise((resolve) => setTimeout(resolve, 150));
    expect(mocks.complete).not.toHaveBeenCalled();
  });

  it("requests path candidates and leaves Enter to the shell by default", async () => {
    const send = await open();
    expect(mocks.complete).toHaveBeenCalledWith(
      `term_${"a".repeat(32)}`, "doc", true, undefined, expect.any(AbortSignal),
    );
    let result!: ReturnType<FakeTerminal["key"]>;
    act(() => { result = owner.key("Enter"); });
    expect(result.passed).toBe(true);
    expect(result.event.preventDefault).not.toHaveBeenCalled();
    expect(send).not.toHaveBeenCalled();
    await waitFor(() => expect(screen.queryByRole("listbox")).toBeNull());
  });

  it("accepts with Tab and claims the DOM event", async () => {
    const send = await open();
    let result!: ReturnType<FakeTerminal["key"]>;
    act(() => { result = owner.key("Tab"); });
    expect(result.passed).toBe(false);
    expect(result.event.preventDefault).toHaveBeenCalled();
    expect(send).toHaveBeenCalledWith("s/");
  });

  it("accepts the arrow-selected row with Enter", async () => {
    const send = await open();
    let arrow!: ReturnType<FakeTerminal["key"]>;
    act(() => { arrow = owner.key("ArrowDown"); });
    expect(arrow.passed).toBe(false);
    await waitFor(() => expect(screen.getAllByRole("option")[1].getAttribute("aria-selected")).toBe("true"));
    let enter!: ReturnType<FakeTerminal["key"]>;
    act(() => { enter = owner.key("Enter"); });
    expect(enter.passed).toBe(false);
    expect(send).toHaveBeenCalledWith("tor/");
  });

  it("explains keyboard controls and formats an unknown truncated directory cleanly", async () => {
    await open([entry("docs")], { directory: null, truncated: true });
    expect(screen.getByText("More results available")).toBeTruthy();
    expect(screen.getByText(/↑↓ choose · Tab complete · Enter run · Esc close/)).toBeTruthy();
  });

  it("dismisses with Escape and never steals an IME key", async () => {
    await open();
    let ime!: ReturnType<FakeTerminal["key"]>;
    let escape!: ReturnType<FakeTerminal["key"]>;
    act(() => {
      ime = owner.key("Enter", { isComposing: true });
      escape = owner.key("Escape");
    });
    expect(ime.passed).toBe(true);
    expect(escape.passed).toBe(false);
    expect(escape.event.preventDefault).toHaveBeenCalled();
  });
});
