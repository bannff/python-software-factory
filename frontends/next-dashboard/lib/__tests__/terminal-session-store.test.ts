import { beforeEach, describe, expect, it } from "vitest";
import { resetTerminalScope, terminalScope } from "../terminal-session-store";

const id = (char: string) => `term_${char.repeat(32)}`;
const ref = (sessionId: string) => ({
  session_id: sessionId, shell: "/bin/zsh", cwd: "/repo",
  cols: 80, rows: 24, alive: true,
});

beforeEach(resetTerminalScope);

describe("global terminal session store", () => {
  it("tracks ordered sessions and the active tab", () => {
    terminalScope.upsert(ref(id("a")));
    terminalScope.upsert(ref(id("b")));
    terminalScope.setActive(id("b"));
    expect(terminalScope.getSessions().map((item) => item.session_id))
      .toEqual([id("a"), id("b")]);
    expect(terminalScope.getActive()).toBe(id("b"));
  });

  it("persists only non-secret session metadata", () => {
    terminalScope.upsert(ref(id("a")));
    const stored = localStorage.getItem("companion-x:terminal:global") ?? "";
    expect(stored).toContain(id("a"));
    expect(stored).not.toContain("ticket");
  });

  it("drops sessions the live backend no longer reports", () => {
    terminalScope.upsert(ref(id("a")));
    terminalScope.upsert(ref(id("b")));
    terminalScope.setActive(id("b"));
    terminalScope.reconcile(new Set([id("a")]));
    expect(terminalScope.getSessions()).toHaveLength(1);
    expect(terminalScope.getActive()).toBe(id("a"));
  });

  it("removes a closed active session and selects the remaining tab", () => {
    terminalScope.upsert(ref(id("a")));
    terminalScope.upsert(ref(id("b")));
    terminalScope.setActive(id("a"));
    terminalScope.remove(id("a"));
    expect(terminalScope.getActive()).toBe(id("b"));
  });
});
