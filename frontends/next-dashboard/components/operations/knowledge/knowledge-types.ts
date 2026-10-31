import { unwrapToolData } from "@/lib/tool-result-data";

export interface KnowledgeDocument {
  id: string;
  source: string;
  content?: string;
  score?: number;
}

export interface KnowledgeStats {
  documentCount: number;
  totalSizeBytes: number;
}

function row(raw: unknown): KnowledgeDocument | null {
  if (!raw || typeof raw !== "object") return null;
  const value = raw as Record<string, unknown>;
  if (typeof value.id !== "string") return null;
  return {
    id: value.id,
    source: typeof value.source === "string" ? value.source : "",
    ...(typeof value.content === "string" ? { content: value.content } : {}),
  };
}

/** Parse ``list_documents`` output: ``{documents: [{id, source}], total}``. */
export function parseDocumentList(raw: unknown): KnowledgeDocument[] {
  const data = unwrapToolData(raw) as { documents?: unknown };
  return Array.isArray(data?.documents)
    ? data.documents.map(row).filter((value): value is KnowledgeDocument => value !== null)
    : [];
}

/** Parse ``search`` output: ``{results: [{document_id, content, score, source}], total}``. */
export function parseSearchResults(raw: unknown): KnowledgeDocument[] {
  const data = unwrapToolData(raw) as { results?: unknown };
  if (!Array.isArray(data?.results)) return [];
  return data.results.flatMap((entry): KnowledgeDocument[] => {
    if (!entry || typeof entry !== "object") return [];
    const value = entry as Record<string, unknown>;
    if (typeof value.document_id !== "string") return [];
    return [{
      id: value.document_id,
      source: typeof value.source === "string" ? value.source : "",
      ...(typeof value.content === "string" ? { content: value.content } : {}),
      ...(typeof value.score === "number" ? { score: value.score } : {}),
    }];
  });
}

/** Parse ``get_collection_stats`` output. */
export function parseStats(raw: unknown): KnowledgeStats | null {
  const data = unwrapToolData(raw) as { document_count?: unknown; total_size_bytes?: unknown };
  if (typeof data?.document_count !== "number") return null;
  return {
    documentCount: data.document_count,
    totalSizeBytes: typeof data.total_size_bytes === "number" ? data.total_size_bytes : 0,
  };
}

/** Parse ``get_document`` output: ``{found, document: {id, content}}``. */
export function parseDocument(raw: unknown): KnowledgeDocument | null {
  const data = unwrapToolData(raw) as { found?: unknown; document?: unknown };
  if (data?.found !== true || !data.document || typeof data.document !== "object") return null;
  const value = data.document as Record<string, unknown>;
  return typeof value.id === "string"
    ? { id: value.id, source: "", ...(typeof value.content === "string" ? { content: value.content } : {}) }
    : null;
}
