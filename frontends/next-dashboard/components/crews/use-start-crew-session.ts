"use client";

import { useCallback, useState } from "react";
import { startCrewSession } from "@/lib/start-crew-session";
import type { Crew } from "./crew-types";

export type StartOutcome = { kind: "started" | "failed"; message: string };

/** Start a session from any Crew via the one shared create path, tracking which card is busy. */
export function useStartCrewSession() {
  const [startingId, setStartingId] = useState<string | null>(null);
  const [outcome, setOutcome] = useState<StartOutcome | null>(null);

  const start = useCallback(async (crew: Crew): Promise<StartOutcome> => {
    setStartingId(crew.id);
    setOutcome(null);
    try {
      await startCrewSession(crew.id);
      const started: StartOutcome = { kind: "started", message: `Session started with ${crew.name}. Find it under Sessions.` };
      setOutcome(started);
      return started;
    } catch (error) {
      const reason = error instanceof Error ? error.message : "Unknown error";
      const failed: StartOutcome = { kind: "failed", message: `Could not start a session with ${crew.name}: ${reason}` };
      setOutcome(failed);
      return failed;
    } finally {
      setStartingId(null);
    }
  }, []);

  const clear = useCallback(() => setOutcome(null), []);

  return { startingId, outcome, start, clear };
}
