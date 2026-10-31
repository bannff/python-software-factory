import { beforeEach, describe, expect, it, vi } from "vitest";
import {
  attachTerminalSession, closeTerminalSession, completeTerminalSession,
  listTerminalShells, openTerminalSession,
} from "../terminal-api";

beforeEach(() => { vi.stubGlobal("fetch", vi.fn()); });

function ok(body: unknown) {
  return { ok: true, json: async () => body } as Response;
}

describe("terminal-api", () => {
  it("opens a session against the guarded BFF with the given spec", async () => {
    const fetchMock = vi.fn().mockResolvedValue(ok({ session: {}, ticket: "t", ws_url: "ws://x" }));
    vi.stubGlobal("fetch", fetchMock);
    await openTerminalSession({ shell: "/bin/zsh" });
    expect(fetchMock).toHaveBeenCalledWith("/api/terminal/sessions", expect.objectContaining({
      method: "POST", body: JSON.stringify({ shell: "/bin/zsh" }),
    }));
  });

  it("attaches to an existing session by id", async () => {
    const fetchMock = vi.fn().mockResolvedValue(ok({ session: {}, ticket: "t", ws_url: "ws://x" }));
    vi.stubGlobal("fetch", fetchMock);
    await attachTerminalSession("term_x");
    expect(fetchMock).toHaveBeenCalledWith("/api/terminal/sessions/term_x/attach", expect.objectContaining({ method: "POST" }));
  });

  it("lists shells and closes a session", async () => {
    const fetchMock = vi.fn()
      .mockResolvedValueOnce(ok({ shells: ["/bin/zsh"] }))
      .mockResolvedValueOnce(ok({ closed: true }));
    vi.stubGlobal("fetch", fetchMock);
    await expect(listTerminalShells()).resolves.toEqual({ shells: ["/bin/zsh"] });
    await expect(closeTerminalSession("term_x")).resolves.toEqual({ closed: true });
    expect(fetchMock.mock.calls[1][0]).toBe("/api/terminal/sessions/term_x");
    expect(fetchMock.mock.calls[1][1]).toMatchObject({ method: "DELETE" });
  });

  it("requests cancellable path and command completions", async () => {
    const fetchMock = vi.fn().mockResolvedValue(ok({ directory: "/tmp", prefix: "d", entries: [], truncated: false }));
    vi.stubGlobal("fetch", fetchMock);
    const controller = new AbortController();
    await completeTerminalSession("term_x", "d", true, ["gh", "pr"], controller.signal);
    expect(fetchMock).toHaveBeenCalledWith(
      "/api/terminal/sessions/term_x/complete",
      expect.objectContaining({
        method: "POST", signal: controller.signal,
        body: JSON.stringify({ token: "d", folders_only: true, argv: ["gh", "pr"] }),
      }),
    );
  });

  it("throws on a non-ok response", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ ok: false, status: 401 }));
    await expect(openTerminalSession()).rejects.toThrow(/401/);
  });
});
