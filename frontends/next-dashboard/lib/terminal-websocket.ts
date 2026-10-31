"use client";

import type { Terminal } from "@xterm/xterm";
import {
  attachTerminalSession, type TerminalSessionRef,
} from "@/lib/terminal-api";

export type TerminalConnectionStatus =
  "connecting" | "connected" | "disconnected" | "displaced";

const encoder = new TextEncoder();

export interface TerminalSocket {
  send(data: string): void;
  resize(cols: number, rows: number): void;
  getStatus(): TerminalConnectionStatus;
  subscribe(listener: () => void): () => void;
  reconnect(): Promise<void>;
  dispose(): void;
}

export async function createTerminalSocket(
  sessionId: string, term: Terminal,
  onSession?: (session: TerminalSessionRef) => void,
): Promise<TerminalSocket> {
  let socket: WebSocket | null = null;
  let status: TerminalConnectionStatus = "connecting";
  let disposed = false;
  let retries = 0;
  let timer: ReturnType<typeof setTimeout> | null = null;
  let connecting: Promise<void> | null = null;
  let generation = 0;
  const listeners = new Set<() => void>();

  const setStatus = (next: TerminalConnectionStatus) => {
    if (status === next) return;
    status = next;
    listeners.forEach((listener) => listener());
  };
  const clearTimer = () => {
    if (timer) clearTimeout(timer);
    timer = null;
  };
  const schedule = () => {
    if (disposed || status === "displaced" || retries >= 10 || timer) return;
    const delay = Math.min(1000 * 2 ** retries, 30_000);
    retries += 1;
    timer = setTimeout(() => {
      timer = null;
      void connect(false).catch(() => schedule());
    }, delay);
  };
  const connect = async (initial: boolean) => {
    if (connecting) return connecting;
    connecting = (async () => {
      clearTimer();
      setStatus("connecting");
      try {
        const attach = await attachTerminalSession(sessionId);
        onSession?.(attach.session);
        if (disposed) return;
        const current = ++generation;
        const ws = new WebSocket(attach.ws_url, [`terminal.${attach.ticket}`]);
        ws.binaryType = "arraybuffer";
        socket = ws;
        ws.onmessage = (event) => {
          if (current !== generation) return;
          if (typeof event.data === "string") {
            try {
              const frame = JSON.parse(event.data) as { code?: unknown };
              if (frame.code === "displaced") {
                clearTimer();
                setStatus("displaced");
              }
            } catch { /* unknown controls are ignored */ }
            return;
          }
          term.write(new Uint8Array(event.data as ArrayBuffer));
        };
        ws.onopen = () => {
          if (current !== generation) return;
          retries = 0;
          setStatus("connected");
          ws.send(JSON.stringify({ type: "resize", cols: term.cols, rows: term.rows }));
        };
        ws.onclose = () => {
          if (current !== generation) return;
          if (socket === ws) socket = null;
          if (disposed || status === "displaced") return;
          setStatus("disconnected");
          schedule();
        };
      } catch (error) {
        setStatus("disconnected");
        if (!initial) schedule();
        throw error;
      }
    })();
    try { await connecting; } finally { connecting = null; }
  };

  await connect(true);
  return {
    send: (data) => {
      // PTY input travels as a BINARY frame. The server routes text frames to
      // the JSON control channel (resize/ping) and silently drops non-JSON text,
      // so sending keystrokes as a string makes the terminal appear dead.
      if (socket?.readyState === WebSocket.OPEN) socket.send(encoder.encode(data));
    },
    resize: (cols, rows) => {
      if (socket?.readyState === WebSocket.OPEN) {
        socket.send(JSON.stringify({ type: "resize", cols, rows }));
      }
    },
    getStatus: () => status,
    subscribe: (listener) => {
      listeners.add(listener);
      return () => listeners.delete(listener);
    },
    reconnect: async () => {
      clearTimer();
      retries = 0;
      if (status !== "displaced" && socket?.readyState === WebSocket.OPEN) return;
      generation += 1;
      socket?.close();
      socket = null;
      await connect(false);
    },
    dispose: () => {
      disposed = true;
      generation += 1;
      clearTimer();
      socket?.close();
      listeners.clear();
    },
  };
}
