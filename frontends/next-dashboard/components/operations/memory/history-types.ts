import { unwrapToolData } from "@/lib/tool-result-data";
import { parseMemoryRow, type MemoryRecord } from "./memory-types";

/** Client view of ``memory_history``'s output (row 47 — Replaced
 * experiences). ``supported: false`` means the active adapter has no
 * supersession substrate to inspect — distinct from a supported adapter
 * reporting a single-entry chain (never replaced). Informational only:
 * no restore action exists here by owner ruling (the curator, not a
 * user, replaces memories). */
export interface MemoryHistory {
  memoryId: string;
  supported: boolean;
  versions: MemoryRecord[];
}

export function parseMemoryHistory(raw: unknown): MemoryHistory {
  const data = unwrapToolData(raw);
  const obj = (data && typeof data === "object" ? data : {}) as Record<string, unknown>;
  const rows = Array.isArray(obj.versions) ? obj.versions : [];
  return {
    memoryId: typeof obj.memory_id === "string" ? obj.memory_id : "",
    supported: obj.supported === true,
    versions: rows.map(parseMemoryRow).filter((row): row is MemoryRecord => row !== null),
  };
}
