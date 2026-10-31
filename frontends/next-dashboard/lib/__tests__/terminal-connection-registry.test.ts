import { afterEach, beforeEach, describe, expect, it, vi, type Mock } from "vitest";

let wsCount = 0;
class FakeWebSocket {
  static OPEN = 1;
  readyState = 1;
  binaryType = "";
  onmessage: ((event: unknown) => void) | null = null;
  onopen: (() => void) | null = null;
  onclose: (() => void) | null = null;
  closed = false;
  constructor(public url: string, public protocols?: string[]) { wsCount += 1; }
  send() {}
  close() { this.closed = true; this.onclose?.(); }
}
(globalThis as unknown as { WebSocket: unknown }).WebSocket = FakeWebSocket;

vi.mock("@xterm/xterm", () => ({
  Terminal: class {
    element?: HTMLElement;
    options: Record<string, unknown> = {};
    cols = 80; rows = 24;
    loadAddon() {}
    open(el: HTMLElement) { this.element = document.createElement("div"); el.appendChild(this.element); }
    onData() { return { dispose() {} }; }
    write() {}
    dispose() {}
  },
}));
vi.mock("@xterm/addon-fit", () => ({ FitAddon: class { activate() {} fit() {} dispose() {} } }));
vi.mock("@xterm/addon-web-links", () => ({ WebLinksAddon: class {} }));
vi.mock("@/lib/terminal-api", () => ({
  attachTerminalSession: vi.fn(async (id: string) => ({
    session: { session_id: id, shell: "/bin/zsh", cwd: "/tmp", cols: 80, rows: 24, alive: true },
    ticket: "tkt", ws_url: "ws://local/term",
  })),
}));

import {
  acquireConnection, disposeConnection, getConnection, resetTerminalConnections,
} from "../terminal-connection-registry";
import { attachTerminalSession } from "@/lib/terminal-api";

const attachMock = attachTerminalSession as unknown as Mock;

beforeEach(() => { wsCount = 0; attachMock.mockClear(); });
afterEach(() => resetTerminalConnections());

describe("terminal connection registry", () => {
  it("reuses one connection and one socket per session id", async () => {
    const first = await acquireConnection("term_a", 14);
    const second = await acquireConnection("term_a", 14);
    expect(first).toBe(second);
    expect(attachMock).toHaveBeenCalledTimes(1);
    expect(wsCount).toBe(1);
  });

  it("does not open a second socket for concurrent acquires", async () => {
    const [a, b] = await Promise.all([
      acquireConnection("term_race", 14), acquireConnection("term_race", 14),
    ]);
    expect(a).toBe(b);
    expect(wsCount).toBe(1);
  });

  it("reparents on attach and parks on detach without reconnecting", async () => {
    const conn = await acquireConnection("term_c", 14);
    const host = document.createElement("div");
    document.body.appendChild(host);
    conn.attach(host);
    expect(conn.term.element?.parentElement).toBe(host);
    conn.detach();
    expect(conn.term.element?.parentElement).not.toBe(host);
    expect(wsCount).toBe(1);
  });

  it("does not let a stale surface detach a newly adopted host", async () => {
    const conn = await acquireConnection("term_move", 14);
    const oldHost = document.createElement("div");
    const newHost = document.createElement("div");
    document.body.append(oldHost, newHost);
    conn.attach(oldHost);
    conn.attach(newHost);
    conn.detach(oldHost);
    expect(conn.term.element?.parentElement).toBe(newHost);
    expect(wsCount).toBe(1);
  });

  it("dispose tears down the connection and a fresh acquire reconnects", async () => {
    await acquireConnection("term_d", 14);
    disposeConnection("term_d");
    expect(getConnection("term_d")).toBeUndefined();
    await acquireConnection("term_d", 14);
    expect(attachMock).toHaveBeenCalledTimes(2);
  });
});
