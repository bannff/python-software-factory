"use client";

import { useCallback, useState } from "react";
import { startCrewSession } from "@/lib/start-crew-session";
import type { Crew } from "./crew-types";

export type StartOutcome = { kind: "started" | "failed"; message: string };

/** Start a session from any Crew via the one shared create path, tracking which card is busy. */
export function useStartCrewSession() {
  const [startingId, setStartingId] = useState<string | null>(null);
  const [outcome, setOutcome] = useState<StartOutcome | null>(null);

  const start = useCallback(async (crew: Crew) => {
    setStartingId(crew.id);
    setOutcome(null);
    try {
      await startCrewSession(crew.id);
      setOutcome({ kind: "started", message: `Session started with ${crew.name}. Find it under Sessions.` });
    } catch (error) {
      const reason = error instanceof Error ? error.message : "Unknown error";
      setOutcome({ kind: "failed", message: `Could not start a session with ${crew.name}: ${reason}` });
    } finally {
      setStartingId(null);
    }
  }, []);

  return { startingId, outcome, start };
}
