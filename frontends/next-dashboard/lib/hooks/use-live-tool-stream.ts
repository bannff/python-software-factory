"use client";

import { useState, useEffect, useRef, useCallback } from "react";
import type { TimelineEntry } from "@/lib/types";
import { mapLiveStreamEvent, type SSEEvent } from "@/lib/live-tool-events";

const MAX_ENTRIES = 50;
const SSE_URL = "/api/events/tools";

// Module-level counter prevents same-ms ID collisions across hook instances
let _counter = 0;

interface LiveToolStreamResult {
  entries: TimelineEntry[];
  connected: boolean;
  frozen: boolean;
  setFrozen: (frozen: boolean) => void;
}
type LiveToolStreamListener = () => void;

interface LiveToolStreamStore {
  entries: TimelineEntry[];
  connected: boolean;
  eventSource: EventSource | null;
}

const store: LiveToolStreamStore = {
  entries: [],
  connected: false,
  eventSource: null,
};

const listeners = new Set<LiveToolStreamListener>();

function notifyListeners() {
  for (const listener of listeners) {
    listener();
  }
}

function pushEntry(entry: TimelineEntry) {
  const existing = store.entries.findIndex((item) => item.id === entry.id);
  store.entries = existing >= 0
    ? store.entries.map((item, index) => index === existing ? entry : item)
    : [entry, ...store.entries].slice(0, MAX_ENTRIES);
  notifyListeners();
}

function nextEventId(ts: number): string {
  return `live-sse-${Math.round(ts * 1000)}-${++_counter}`;
}

function setConnected(connected: boolean) {
  if (store.connected === connected) return;
  store.connected = connected;
  notifyListeners();
}

function ensureStream() {
  if (store.eventSource || typeof window === "undefined") return;
  // Some environments (jsdom tests, SSR) have no EventSource — degrade to a
  // disconnected stream rather than throwing during render.
  if (typeof EventSource === "undefined") return;

  const eventSource = new EventSource(SSE_URL);
  store.eventSource = eventSource;

  eventSource.onopen = () => {
    setConnected(true);
  };

  eventSource.onmessage = (e) => {
    try {
      const data = JSON.parse(e.data) as SSEEvent;
      const id = "invocation_id" in data && data.invocation_id
        ? `live-tool-${data.invocation_id}`
        : nextEventId(data.ts);
      pushEntry(mapLiveStreamEvent(data, id));
    } catch {
      // malformed event — ignore
    }
  };

  eventSource.onerror = () => {
    setConnected(false);
  };
}

function subscribe(listener: LiveToolStreamListener) {
  listeners.add(listener);
  return () => {
    listeners.delete(listener);
  };
}

export function useLiveToolStream(): LiveToolStreamResult {
  const [entries, setEntries] = useState<TimelineEntry[]>(() => store.entries);
  const [connected, setConnectedState] = useState(store.connected);
  const [frozen, setFrozen] = useState(false);
  const frozenRef = useRef(frozen);
  const pendingRef = useRef<TimelineEntry[]>([]);
  const latestEntryIdRef = useRef<string | null>(store.entries[0]?.id ?? null);

  // Keep frozenRef in sync without re-creating the effect
  useEffect(() => { frozenRef.current = frozen; }, [frozen]);

  // Flush pending entries when unfreezing
  const handleSetFrozen = useCallback((next: boolean) => {
    setFrozen(next);
    if (!next && pendingRef.current.length > 0) {
      setEntries(() => {
        const merged = [...pendingRef.current, ...store.entries].slice(0, MAX_ENTRIES);
        pendingRef.current = [];
        latestEntryIdRef.current = merged[0]?.id ?? null;
        return merged;
      });
    }
  }, []);

  useEffect(() => {
    ensureStream();

    const syncFromStore = () => {
      setConnectedState(store.connected);

      if (frozenRef.current) {
        const lastSeenId = latestEntryIdRef.current;
        const cutoff = lastSeenId
          ? store.entries.findIndex((entry) => entry.id === lastSeenId)
          : -1;
        const freshEntries = cutoff === -1
          ? store.entries
          : store.entries.slice(0, cutoff);

        if (freshEntries.length > 0) {
          pendingRef.current = [...freshEntries, ...pendingRef.current].slice(0, MAX_ENTRIES);
        }
        return;
      }

      setEntries(store.entries);
      latestEntryIdRef.current = store.entries[0]?.id ?? null;
    };

    syncFromStore();
    return subscribe(syncFromStore);
  }, []);

  return { entries, connected, frozen, setFrozen: handleSetFrozen };
}
