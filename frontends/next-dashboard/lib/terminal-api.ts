export interface TerminalSessionRef {
  session_id: string;
  shell: string;
  cwd: string;
  cols: number;
  rows: number;
  alive: boolean;
}

export interface TerminalAttach {
  session: TerminalSessionRef;
  ticket: string;
  ws_url: string;
}

async function call<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`/api/terminal${path}`, {
    ...init,
    headers: {
      "content-type": "application/json",
      "x-companion-x-local": "1",
      ...(init?.headers ?? {}),
    },
    cache: "no-store",
  });
  if (!response.ok) throw new Error(`terminal request failed: ${response.status}`);
  return response.json() as Promise<T>;
}

export interface TerminalOpenSpec {
  shell?: string;
  cwd?: string;
  cols?: number;
  rows?: number;
}

export function openTerminalSession(
  spec: TerminalOpenSpec = {},
): Promise<TerminalAttach> {
  return call<TerminalAttach>("/sessions", {
    method: "POST", body: JSON.stringify(spec),
  });
}

export function attachTerminalSession(sessionId: string): Promise<TerminalAttach> {
  return call<TerminalAttach>(`/sessions/${sessionId}/attach`, { method: "POST", body: "{}" });
}

export function listTerminalSessions(): Promise<{ sessions: TerminalSessionRef[] }> {
  return call("/sessions");
}

export function listTerminalShells(): Promise<{ shells: string[] }> {
  return call("/shells");
}

export function closeTerminalSession(sessionId: string): Promise<{ closed: boolean }> {
  return call(`/sessions/${sessionId}`, { method: "DELETE" });
}

export interface TerminalCompletionEntry {
  name: string;
  dir: boolean;
  at: number;
  kind: "sub" | "flag" | null;
  description: string | null;
  nospace: boolean;
}

export interface TerminalCompletionResult {
  directory: string | null;
  prefix: string;
  entries: TerminalCompletionEntry[];
  truncated: boolean;
}

export function completeTerminalSession(
  sessionId: string, token: string, foldersOnly: boolean, argv?: string[],
  signal?: AbortSignal,
): Promise<TerminalCompletionResult> {
  return call(`/sessions/${sessionId}/complete`, {
    method: "POST", signal,
    body: JSON.stringify({
      token, folders_only: foldersOnly, ...(argv ? { argv } : {}),
    }),
  });
}
