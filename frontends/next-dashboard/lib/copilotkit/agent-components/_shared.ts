import { unwrapToolResult } from "@companion-x/shared-renderer";

/**
 * Shared helpers for agent-components/* (bd-kzsl Phase 1).
 *
 * Stays a pure-data module so each per-component file can import the
 * small set of utilities without pulling React.
 */

export const SEVERITY_COLOR: Record<string, string> = {
  critical: "bg-red-500/15 text-red-600 dark:text-red-300 border-red-500/40",
  high: "bg-red-500/15 text-red-600 dark:text-red-300 border-red-500/40",
  medium: "bg-amber-500/15 text-amber-600 dark:text-amber-300 border-amber-500/40",
  low: "bg-blue-500/15 text-blue-600 dark:text-blue-300 border-blue-500/40",
  info: "bg-muted text-muted-foreground border-border",
};

/** Unwrap gateway wrappers and fail closed on MCP tool failures. */
export function unwrap(raw: unknown): unknown {
  return unwrapToolResult(raw);
}
