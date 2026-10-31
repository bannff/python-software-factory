/**
 * Browser-side MCP connection status store. Shared by the client (which owns
 * the handshake and the failure cause), the `useMcpConnection` hook, and the
 * composer gate that renders the state.
 */

export type McpConnectionStatus = "idle" | "connecting" | "connected" | "error";

export interface McpConnectionState {
  status: McpConnectionStatus;
  /** Human-readable cause of the last failed attempt, `null` when healthy. */
  error: string | null;
}

const IDLE: McpConnectionState = { status: "idle", error: null };
let state: McpConnectionState = IDLE;
const listeners = new Set<() => void>();

/** Stable snapshot for `useSyncExternalStore` — identity changes on every transition. */
export function getMcpConnectionState(): McpConnectionState {
  return state;
}

export function subscribeMcpConnection(listener: () => void): () => void {
  listeners.add(listener);
  return () => listeners.delete(listener);
}

export function setMcpConnectionStatus(
  status: McpConnectionStatus,
  cause: string | null = null,
): void {
  if (state.status === status && state.error === cause) return;
  state = status === "idle" && cause === null ? IDLE : { status, error: cause };
  listeners.forEach((listener) => listener());
}
