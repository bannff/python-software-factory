"use client";

/**
 * useRunStream — subscribes to per-run SSE endpoint and returns live events.
 * bd:python-factory-r3eqj P2c
 *
 * Mirrors the singleton pattern of use-live-tool-stream.ts but scoped to a
 * single run_id. Each hook instance owns its own EventSource — no shared
 * store needed since run windows are unique per run.
 *
 * SSE endpoint: GET /api/stream/run/{run_id}  (wired in P2a)
 * Event shape on the wire: JSON lines published by the events brick,
 * tagged with run_id. The background task wraps each Strands event in a
 * spawn.event envelope:
 *   { event_type: "spawn.event", run_id, agent_id, event: <raw_strands_ev> }
 * Completion is signalled by:
 *   { event_type: "swarm.completed", ... }  OR  { status: "completed", ... }
 */

import { useState, useEffect, useRef } from "react";

const MAX_EVENTS = 50;

export interface RunStreamEvent {
  event_type?: string;
  type?: string;
  run_id?: string;
  agent_id?: string;
  /** spawn.event carries inner Strands event dict */
  event?: Record<string, unknown>;
  error?: string;
  status?: string;
}

export interface RunStreamResult {
  events: RunStreamEvent[];
  connected: boolean;
  /** true once swarm.completed or status=completed arrives */
  completed: boolean;
}

function isCompleted(ev: RunStreamEvent): boolean {
  return (
    ev.event_type === "swarm.completed" ||
    ev.status === "completed"
  );
}

/**
 * Subscribes to /api/stream/run/{runId} when runId is non-null.
 * Cleans up the EventSource on unmount or runId change.
 * No reconnect logic in v1 — the SSE endpoint is short-lived per run.
 */
export function useRunStream(runId: string | null): RunStreamResult {
  const [events, setEvents] = useState<RunStreamEvent[]>([]);
  const [connected, setConnected] = useState(false);
  const [completed, setCompleted] = useState(false);
  // Ref so the cleanup closure always sees the latest ES instance.
  const esRef = useRef<EventSource | null>(null);

  useEffect(() => {
    if (!runId || typeof window === "undefined") return;

    // Reset state for new runId
    setEvents([]);
    setConnected(false);
    setCompleted(false);

    const url = `/api/stream/run/${encodeURIComponent(runId)}`;
    const es = new EventSource(url);
    esRef.current = es;

    es.onopen = () => {
      setConnected(true);
    };

    es.onmessage = (e: MessageEvent) => {
      try {
        const data = JSON.parse(e.data) as RunStreamEvent;
        setEvents((prev) =>
          [...prev, data].slice(-MAX_EVENTS)
        );
        if (isCompleted(data)) {
          setCompleted(true);
          setConnected(false);
          es.close();
          esRef.current = null;
        }
      } catch {
        // malformed event — ignore
      }
    };

    es.onerror = () => {
      setConnected(false);
    };

    return () => {
      es.close();
      esRef.current = null;
    };
  }, [runId]);

  return { events, connected, completed };
}
