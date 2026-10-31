import { describe, expect, it, beforeEach } from "vitest";
import {
  getTerminalSessions, recordTerminalSession, resetTerminalSessions,
  type TerminalSession,
} from "../terminal-store";

function session(run: number, over: Partial<TerminalSession> = {}): TerminalSession {
  return {
    run_id: `cmd_${String(run).padStart(32, "0")}`,
    status: "completed",
    command: run === 1 ? "pytest" : "git",
    cwd: "/workspace/project",
    stdout: run === 1 ? "2 passed\n" : "clean\n",
    stderr: "",
    started_at: run,
    completed_at: run + 1,
    exit_code: 0,
    duration_ms: 25,
    truncated: false,
    ...over,
  };
}

beforeEach(resetTerminalSessions);

describe("terminal-store", () => {
  it("caps retained one-shot command sessions at twenty, newest first", () => {
    for (let index = 1; index <= 25; index += 1) recordTerminalSession(session(index));
    expect(getTerminalSessions()).toHaveLength(20);
    expect(getTerminalSessions()[0].run_id).toBe(session(25).run_id);
  });
});
