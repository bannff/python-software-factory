import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const mocks = vi.hoisted(() => ({ attach: vi.fn() }));
vi.mock("@/lib/terminal-api", () => ({
  attachTerminalSession: (...args: unknown[]) => mocks.attach(...args),
}));
import { createTerminalSocket } from "../terminal-websocket";

const sockets: FakeWebSocket[] = [];
class FakeWebSocket {
  static OPEN = 1;
  readyState = 0;
  binaryType = "";
  onmessage: ((event: { data: unknown }) => void) | null = null;
  onopen: (() => void) | null = null;
  onclose: (() => void) | null = null;
  send = vi.fn();
  constructor(public url: string, public protocols: string[]) { sockets.push(this); }
  open() { this.readyState = 1; this.onopen?.(); }
  message(data: unknown) { this.onmessage?.({ data }); }
  close() { this.readyState = 3; this.onclose?.(); }
}
(globalThis as unknown as { WebSocket: unknown }).WebSocket = FakeWebSocket;

const term = { cols: 80, rows: 24, write: vi.fn() };

beforeEach(() => {
  sockets.length = 0;
  mocks.attach.mockReset().mockImplementation(async () => ({
    session: { session_id: "term_a", shell: "/bin/zsh", cwd: "/tmp", cols: 80, rows: 24, alive: true },
    ticket: `ticket-${sockets.length}`, ws_url: "ws://terminal",
  }));
});
afterEach(() => vi.useRealTimers());

describe("terminal websocket", () => {
  it("parks on displacement and manually reconnects without stale close regression", async () => {
    const channel = await createTerminalSocket("term_a", term as never);
    sockets[0].open();
    expect(channel.getStatus()).toBe("connected");
    sockets[0].message(JSON.stringify({ type: "error", code: "displaced" }));
    expect(channel.getStatus()).toBe("displaced");

    await channel.reconnect();
    expect(sockets).toHaveLength(2);
    sockets[0].onclose?.();
    expect(channel.getStatus()).toBe("connecting");
    sockets[1].open();
    expect(channel.getStatus()).toBe("connected");
    channel.dispose();
  });

  it("automatically reconnects an ordinary disconnect with bounded backoff", async () => {
    vi.useFakeTimers();
    const channel = await createTerminalSocket("term_a", term as never);
    sockets[0].open();
    sockets[0].close();
    expect(channel.getStatus()).toBe("disconnected");
    await vi.advanceTimersByTimeAsync(1000);
    expect(sockets).toHaveLength(2);
    channel.dispose();
  });
});
