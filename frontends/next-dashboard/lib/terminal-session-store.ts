import type { TerminalSessionRef } from "@/lib/terminal-api";

const STORAGE_KEY = "companion-x:terminal:global";
let sessions: readonly TerminalSessionRef[] = [];
let active: string | null = null;
let hydrated = false;
const listeners = new Set<() => void>();

function valid(value: unknown): value is TerminalSessionRef {
  if (!value || typeof value !== "object") return false;
  const row = value as Record<string, unknown>;
  return /^term_[0-9a-f]{32}$/.test(String(row.session_id))
    && typeof row.shell === "string" && typeof row.cwd === "string"
    && typeof row.cols === "number" && typeof row.rows === "number"
    && typeof row.alive === "boolean";
}

function freeze(session: TerminalSessionRef): TerminalSessionRef {
  return Object.freeze({
    session_id: session.session_id, shell: session.shell, cwd: session.cwd,
    cols: session.cols, rows: session.rows, alive: session.alive,
  });
}

function hydrate(): void {
  if (hydrated) return;
  hydrated = true;
  try {
    if (typeof localStorage === "undefined") return;
    const parsed = JSON.parse(localStorage.getItem(STORAGE_KEY) ?? "null") as {
      sessions?: unknown; active?: unknown;
    } | null;
    sessions = Object.freeze(
      Array.isArray(parsed?.sessions) ? parsed.sessions.filter(valid).map(freeze) : [],
    );
    active = typeof parsed?.active === "string"
      && sessions.some((item) => item.session_id === parsed.active)
      ? parsed.active : sessions[0]?.session_id ?? null;
  } catch { sessions = []; active = null; }
}

function persist(): void {
  try {
    localStorage?.setItem(STORAGE_KEY, JSON.stringify({ sessions, active }));
  } catch { /* persistence is best-effort */ }
}

function emit(): void {
  persist();
  listeners.forEach((listener) => listener());
}

export const terminalScope = {
  upsert(session: TerminalSessionRef): void {
    hydrate();
    sessions = Object.freeze([
      ...sessions.filter((item) => item.session_id !== session.session_id),
      freeze(session),
    ]);
    if (!active) active = session.session_id;
    emit();
  },
  remove(sessionId: string): void {
    hydrate();
    sessions = Object.freeze(sessions.filter((item) => item.session_id !== sessionId));
    if (active === sessionId) active = sessions[0]?.session_id ?? null;
    emit();
  },
  setActive(sessionId: string | null): void { hydrate(); active = sessionId; emit(); },
  getSessions(): readonly TerminalSessionRef[] { hydrate(); return sessions; },
  getActive(): string | null { hydrate(); return active; },
  subscribe(listener: () => void): () => void {
    listeners.add(listener);
    return () => listeners.delete(listener);
  },
  reconcile(liveIds: ReadonlySet<string>): void {
    hydrate();
    const next = sessions.filter((item) => liveIds.has(item.session_id));
    if (next.length === sessions.length) return;
    sessions = Object.freeze(next);
    if (active && !liveIds.has(active)) active = next[0]?.session_id ?? null;
    emit();
  },
};

export function resetTerminalScope(): void {
  sessions = [];
  active = null;
  hydrated = false;
  listeners.clear();
  try { localStorage?.removeItem(STORAGE_KEY); } catch { /* ignore */ }
}
