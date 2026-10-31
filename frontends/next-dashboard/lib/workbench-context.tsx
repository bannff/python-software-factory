"use client";

/**
 * Workbench state lifted to a React context above <CopilotKitProvider>.
 *
 * Consumers (chat sidebar, status bar, page content) all read from the
 * same provider so the canvas-aware chat (bd-vw04) can publish workbench
 * state into the agent context via useAgentContext, and the FE-tool
 * round-trip (bd-115z) can drive the same workbench from inside the
 * provider tree.
 *
 * Drop-in for the existing `useWorkbench` hook — `useWorkbenchContext`
 * returns the exact same shape.
 */

import { createContext, useContext, type ReactNode } from "react";
import { useWorkbench } from "@/lib/hooks/use-workbench";

type WorkbenchValue = ReturnType<typeof useWorkbench>;

const WorkbenchContext = createContext<WorkbenchValue | null>(null);

export function WorkbenchProvider({ children }: { children: ReactNode }) {
  const value = useWorkbench();
  return (
    <WorkbenchContext.Provider value={value}>
      {children}
    </WorkbenchContext.Provider>
  );
}

export function useWorkbenchContext(): WorkbenchValue {
  const ctx = useContext(WorkbenchContext);
  if (ctx === null) {
    throw new Error(
      "useWorkbenchContext must be used inside <WorkbenchProvider>"
    );
  }
  return ctx;
}

/** Same value, or null when rendered outside the provider (embedded/tests). */
export function useOptionalWorkbenchContext(): WorkbenchValue | null {
  return useContext(WorkbenchContext);
}
