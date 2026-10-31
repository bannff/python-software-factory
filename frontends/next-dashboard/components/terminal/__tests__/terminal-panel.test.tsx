import { StrictMode } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";

const mocks = vi.hoisted(() => ({
  display: {
    preferences: {
      theme: "dark", terminalFontSize: 14, terminalShell: "/bin/bash",
      terminalCompletionEnabled: true, density: "comfortable", language: "en", shortcuts: {}, revision: 1,
    },
    loading: false,
  },
  openSession: vi.fn(),
  liveSessions: [] as Array<{
    session_id: string; shell: string; cwd: string;
    cols: number; rows: number; alive: boolean;
  }>,
}));
vi.mock("@/components/settings/use-display-preferences", () => ({
  useDisplayPreferences: () => ({ ...mocks.display, error: null, refresh: vi.fn() }),
}));
vi.mock("@/lib/terminal-api", () => ({
  openTerminalSession: (...args: unknown[]) => mocks.openSession(...args),
  listTerminalSessions: vi.fn(async () => ({ sessions: mocks.liveSessions })),
  listTerminalShells: vi.fn(async () => ({ shells: ["/bin/zsh", "/bin/bash"] })),
  closeTerminalSession: vi.fn(async () => ({ closed: true })),
}));
vi.mock("@/lib/hooks/use-terminal-session", () => ({
  useTerminalMount: () => [{ current: null }, {
    term: { options: {} }, send: vi.fn(), getStatus: () => "connected",
    subscribe: () => () => {}, reconnect: vi.fn(),
  }],
}));
vi.mock("../terminal-completion", () => ({ TerminalCompletion: () => null }));

import { TerminalPanel } from "../terminal-panel";
import { resetTerminalScope } from "@/lib/terminal-session-store";

const session = (index: number, shell = "/bin/zsh") => ({
  session_id: `term_${index.toString(16).padStart(32, "0")}`,
  shell, cwd: "/repo", cols: 80, rows: 24, alive: true,
});

beforeEach(() => {
  resetTerminalScope();
  mocks.display.loading = false;
  mocks.liveSessions = [];
  let index = 0;
  mocks.openSession.mockReset().mockImplementation(async (spec = {}) => ({
    session: session(++index, (spec as { shell?: string }).shell ?? "/bin/zsh"),
    ticket: "ticket", ws_url: "ws://terminal",
  }));
});

describe("TerminalPanel", () => {
  it("opens the saved shell exactly once across a StrictMode remount", async () => {
    mocks.display.loading = true;
    const view = render(<StrictMode><TerminalPanel onClose={vi.fn()} /></StrictMode>);
    expect(mocks.openSession).not.toHaveBeenCalled();
    mocks.display.loading = false;
    view.rerender(<StrictMode><TerminalPanel onClose={vi.fn()} /></StrictMode>);
    await waitFor(() => expect(mocks.openSession).toHaveBeenCalledTimes(1));
    expect(mocks.openSession).toHaveBeenCalledWith({ shell: "/bin/bash" });
    expect(await screen.findByRole("tab", { name: "bash" })).toBeTruthy();
  });

  it("the plus button opens another default-shell tab", async () => {
    render(<TerminalPanel onClose={vi.fn()} />);
    await screen.findByRole("tab", { name: "bash" });
    fireEvent.click(screen.getByRole("button", { name: "New terminal session" }));
    await waitFor(() => expect(mocks.openSession).toHaveBeenCalledTimes(2));
    expect(screen.getAllByRole("tab")).toHaveLength(2);
  });

  it("the shell picker opens the selected shell tab", async () => {
    render(<TerminalPanel onClose={vi.fn()} />);
    await screen.findByRole("tab", { name: "bash" });
    fireEvent.change(screen.getByRole("combobox", { name: "Open shell" }), {
      target: { value: "/bin/zsh" },
    });
    await waitFor(() => expect(mocks.openSession).toHaveBeenLastCalledWith({ shell: "/bin/zsh" }));
    expect(await screen.findByRole("tab", { name: "zsh" })).toBeTruthy();
  });

  it("closes the bottom dock through its owner callback", async () => {
    const close = vi.fn();
    render(<TerminalPanel onClose={close} />);
    await screen.findByRole("tab", { name: "bash" });
    fireEvent.click(screen.getByRole("button", { name: "Close Terminal" }));
    expect(close).toHaveBeenCalledOnce();
  });
});
