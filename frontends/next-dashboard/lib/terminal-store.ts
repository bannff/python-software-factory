export type TerminalStatus = "running" | "completed" | "failed" | "cancelled" | "timed_out";

export interface TerminalSession {
  run_id: string;
  status: TerminalStatus;
  command: string;
  cwd: string;
  stdout: string;
  stderr: string;
  started_at: number;
  completed_at?: number | null;
  exit_code?: number | null;
  duration_ms?: number | null;
  truncated: boolean;
}

const MAX_SESSIONS = 20;
let sessions: readonly TerminalSession[] = [];
const listeners = new Set<() => void>();

export function recordTerminalSession(session: TerminalSession): void {
  const snapshot = Object.freeze({ ...session });
  sessions = Object.freeze([
    snapshot,
    ...sessions.filter((item) => item.run_id !== session.run_id),
  ].slice(0, MAX_SESSIONS));
  listeners.forEach((listener) => listener());
}

export function getTerminalSessions(): readonly TerminalSession[] {
  return sessions;
}

export function subscribeTerminalSessions(listener: () => void): () => void {
  listeners.add(listener);
  return () => listeners.delete(listener);
}

export function resetTerminalSessions(): void {
  sessions = [];
  listeners.forEach((listener) => listener());
}
