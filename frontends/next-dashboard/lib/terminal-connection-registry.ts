import type { TerminalSessionRef } from "@/lib/terminal-api";
import {
  createTerminalSocket, type TerminalConnectionStatus,
} from "@/lib/terminal-websocket";
import type { Terminal } from "@xterm/xterm";
import type { FitAddon } from "@xterm/addon-fit";

/**
 * Module-scope registry of live terminal connections, keyed by PTY session id.
 *
 * Each connection owns one xterm instance and one WebSocket for the lifetime
 * of the session. When the bottom dock mounts it reparents the existing xterm
 * element into its container and refits; when it unmounts the element is parked
 * in an off-screen holder that keeps a stable, non-zero size so xterm never
 * refits to 0x0. This preserves the live shell across dock close/reopen and
 * route changes without opening a second socket.
 *
 * The registry is keyed only by server-issued session id; transport reconnects
 * are generation-guarded so stale callbacks cannot replace the live socket.
 */

export type { TerminalConnectionStatus } from "@/lib/terminal-websocket";

export interface TerminalConnection {
  readonly sessionId: string;
  readonly term: Terminal;
  readonly fit: FitAddon;
  send(data: string): void;
  refit(): void;
  attach(el: HTMLElement): void;
  detach(el?: HTMLElement): void;
  getStatus(): TerminalConnectionStatus;
  subscribe(listener: () => void): () => void;
  reconnect(): Promise<void>;
  dispose(): void;
}

const connections = new Map<string, TerminalConnection>();
const pending = new Map<string, Promise<TerminalConnection>>();

let holder: HTMLDivElement | null = null;

function offscreenHolder(): HTMLDivElement {
  if (holder && holder.isConnected) return holder;
  holder = document.createElement("div");
  holder.setAttribute("data-terminal-holder", "");
  // Stable non-zero box so a parked terminal never fits to 0x0.
  holder.style.cssText =
    "position:absolute;left:-99999px;top:0;width:800px;height:400px;overflow:hidden;";
  document.body.appendChild(holder);
  return holder;
}

async function createConnection(
  sessionId: string, fontSize: number,
  onSession?: (session: TerminalSessionRef) => void,
): Promise<TerminalConnection> {
  // xterm and its addons touch browser globals at load time, so import them
  // lazily inside this client-only path (never at module scope → no SSR crash).
  const [{ Terminal: TerminalCtor }, { FitAddon: FitAddonCtor }, { WebLinksAddon }] =
    await Promise.all([
      import("@xterm/xterm"), import("@xterm/addon-fit"), import("@xterm/addon-web-links"),
    ]);
  const term = new TerminalCtor({
    fontSize, fontFamily: "ui-monospace, SFMono-Regular, monospace",
    convertEol: false, cursorBlink: true,
  });
  const fit = new FitAddonCtor();
  term.loadAddon(fit);
  term.loadAddon(new WebLinksAddon());
  term.open(offscreenHolder());

  let mounted: HTMLElement | null = null;
  const channel = await createTerminalSocket(sessionId, term, onSession);
  const dataListener = term.onData((data) => channel.send(data));

  const refit = () => {
    const host = mounted;
    if (!host || host.clientWidth === 0 || host.clientHeight === 0) return;
    fit.fit();
    channel.resize(term.cols, term.rows);
  };

  return {
    sessionId, term, fit,
    send: channel.send,
    refit,
    attach: (el) => {
      const node = term.element;
      if (node && node.parentElement !== el) el.appendChild(node);
      mounted = el;
      refit();
    },
    detach: (el) => {
      if (el && mounted !== el) return;
      const node = term.element;
      if (node) offscreenHolder().appendChild(node); // park; do NOT refit to 0x0
      mounted = null;
    },
    getStatus: channel.getStatus,
    subscribe: channel.subscribe,
    reconnect: channel.reconnect,
    dispose: () => {
      channel.dispose();
      dataListener.dispose();
      term.dispose();
      connections.delete(sessionId);
    },
  };
}

/** Return the existing connection for a session, or create one exactly once. */
export function acquireConnection(
  sessionId: string, fontSize: number,
  onSession?: (session: TerminalSessionRef) => void,
): Promise<TerminalConnection> {
  const existing = connections.get(sessionId);
  if (existing) return Promise.resolve(existing);
  const inFlight = pending.get(sessionId);
  if (inFlight) return inFlight;
  const created = createConnection(sessionId, fontSize, onSession)
    .then((connection) => { connections.set(sessionId, connection); pending.delete(sessionId); return connection; })
    .catch((error) => { pending.delete(sessionId); throw error; });
  pending.set(sessionId, created);
  return created;
}

export function getConnection(sessionId: string): TerminalConnection | undefined {
  return connections.get(sessionId);
}

/** Tear down a connection's socket + xterm (caller issues the DELETE). */
export function disposeConnection(sessionId: string): void {
  const existing = connections.get(sessionId);
  if (existing) { existing.dispose(); return; }
  const inFlight = pending.get(sessionId);
  if (inFlight) void inFlight.then((connection) => connection.dispose()).catch(() => {});
}

/** Test-only: dispose every connection and reset the registry. */
export function resetTerminalConnections(): void {
  connections.forEach((connection) => connection.dispose());
  connections.clear();
  pending.clear();
  holder?.remove();
  holder = null;
}
