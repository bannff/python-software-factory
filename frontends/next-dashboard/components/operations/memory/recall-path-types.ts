import { unwrapToolData } from "@/lib/tool-result-data";
import { parseMemoryRow, type MemoryRecord } from "./memory-types";

/** Client view of ``memory_recall_inspect``'s output (row 45's recall
 * inspection, owner direction 2026-09-16): the real owner/chain/similarity
 * edges around one memory. ``supported: false`` means the active adapter
 * has no graph substrate to inspect (e.g. the plain in-memory adapter) —
 * distinct from a supported adapter reporting an empty neighborhood. */
export interface SimilarMemory {
  memory: MemoryRecord;
  score: number | null;
}

export interface RecallPath {
  memoryId: string;
  supported: boolean;
  ownerId: string | null;
  followed: MemoryRecord | null;
  similar: SimilarMemory[];
}

function parseSimilar(row: unknown): SimilarMemory | null {
  if (!row || typeof row !== "object") return null;
  const r = row as Record<string, unknown>;
  const memory = parseMemoryRow(r.memory);
  if (!memory) return null;
  return { memory, score: typeof r.score === "number" ? r.score : null };
}

export function parseRecallPath(raw: unknown): RecallPath {
  const data = unwrapToolData(raw);
  const obj = (data && typeof data === "object" ? data : {}) as Record<string, unknown>;
  const similarRows = Array.isArray(obj.similar) ? obj.similar : [];
  return {
    memoryId: typeof obj.memory_id === "string" ? obj.memory_id : "",
    supported: obj.supported === true,
    ownerId: typeof obj.owner_id === "string" ? obj.owner_id : null,
    followed: parseMemoryRow(obj.followed),
    similar: similarRows.map(parseSimilar).filter((row): row is SimilarMemory => row !== null),
  };
}
