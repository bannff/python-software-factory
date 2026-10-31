import { useEffect, useRef, useState } from "react";
import type { TerminalSessionRef } from "@/lib/terminal-api";
import {
  acquireConnection, getConnection, type TerminalConnection,
} from "@/lib/terminal-connection-registry";

/** Refit the connection whenever its host element resizes (skips 0x0). */
export function useTerminalResize(
  connection: TerminalConnection | null, element: HTMLDivElement | null,
) {
  useEffect(() => {
    if (!connection || !element) return;
    const observer = new ResizeObserver(() => connection.refit());
    observer.observe(element);
    return () => observer.disconnect();
  }, [connection, element]);
}

interface MountOptions {
  onSession?: (session: TerminalSessionRef) => void;
  /** Invoked when attach fails — the session is dead and should be dropped. */
  onDead?: (sessionId: string) => void;
}

/**
 * Mount the active session's xterm into a container by reparenting its
 * registry-owned connection. Switching `sessionId` parks the previous
 * terminal (keeping its socket) and reparents the next — it never disposes,
 * so no second socket is opened on remount, tab switch, or scope move.
 */
export function useTerminalMount(
  sessionId: string | null, fontSize: number, options: MountOptions = {},
): [React.RefObject<HTMLDivElement | null>, TerminalConnection | null] {
  const container = useRef<HTMLDivElement>(null);
  const [connection, setConnection] = useState<TerminalConnection | null>(null);
  const optionsRef = useRef(options);
  optionsRef.current = options;

  useEffect(() => {
    const el = container.current;
    if (!sessionId || !el) { setConnection(null); return; }
    let cancelled = false;
    acquireConnection(sessionId, fontSize, optionsRef.current.onSession)
      .then((next) => {
        if (cancelled) return;
        next.attach(el);
        setConnection(next);
      })
      .catch(() => {
        if (!cancelled) { setConnection(null); optionsRef.current.onDead?.(sessionId); }
      });
    return () => {
      cancelled = true;
      getConnection(sessionId)?.detach(el);
      setConnection(null);
    };
    // fontSize is applied via the caller's effect on `term.options`; re-running
    // this on font change would needlessly detach/reparent the live terminal.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [sessionId]);

  useTerminalResize(connection, container.current);
  return [container, connection];
}
