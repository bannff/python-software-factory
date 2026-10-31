"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { callTool } from "@/lib/api";
import {
  parseDocument, parseDocumentList, parseSearchResults, parseStats,
  type KnowledgeDocument, type KnowledgeStats,
} from "./knowledge-types";

/**
 * Knowledge library (feature-map row 38): browse/search KB documents,
 * ingest new ones, delete, and see collection stats — backed by the real
 * ``kb_list_documents``/``kb_search``/``kb_ingest``/``kb_delete_document``/
 * ``kb_get_collection_stats`` MCP tools (all already exist; this is a pure
 * FE gap, same shape as the Memory browser's own history).
 *
 * A text query switches the read path from ``kb_list_documents`` (plain
 * paged browse) to ``kb_search`` (relevance-scored) — mirrors Memory's
 * list/retrieve split so both render through the same list shape.
 */
export function useKnowledge() {
  const [documents, setDocuments] = useState<KnowledgeDocument[]>([]);
  const [stats, setStats] = useState<KnowledgeStats | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [query, setQuery] = useState("");
  const mounted = useRef(true);

  const refresh = useCallback(async (nextQuery = query) => {
    setLoading(true);
    try {
      const raw = nextQuery.trim()
        ? await callTool("kb_search", { query: nextQuery.trim(), limit: 50 })
        : await callTool("kb_list_documents", { limit: 200 });
      const parsed = nextQuery.trim() ? parseSearchResults(raw) : parseDocumentList(raw);
      if (!mounted.current) return;
      setDocuments(parsed);
      setError(null);
    } catch {
      if (mounted.current) setError("Knowledge library unavailable");
    } finally {
      if (mounted.current) setLoading(false);
    }
  }, [query]);

  const refreshStats = useCallback(async () => {
    try {
      const raw = await callTool("kb_get_collection_stats", {});
      if (mounted.current) setStats(parseStats(raw));
    } catch {
      // Stats are supplementary; a failure here never blocks the document list.
    }
  }, []);

  useEffect(() => {
    mounted.current = true;
    void refresh();
    void refreshStats();
    return () => { mounted.current = false; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const search = useCallback((nextQuery: string) => {
    setQuery(nextQuery);
    void refresh(nextQuery);
  }, [refresh]);

  const ingest = useCallback(async (content: string, source?: string): Promise<boolean> => {
    try {
      await callTool("kb_ingest", { content, ...(source ? { source } : {}) });
      await refresh();
      await refreshStats();
      return true;
    } catch {
      return false;
    }
  }, [refresh, refreshStats]);

  const remove = useCallback(async (documentId: string): Promise<boolean> => {
    try {
      await callTool("kb_delete_document", { document_id: documentId });
      await refresh();
      await refreshStats();
      return true;
    } catch {
      return false;
    }
  }, [refresh, refreshStats]);

  const getDocument = useCallback(async (documentId: string): Promise<KnowledgeDocument | null> => {
    try {
      return parseDocument(await callTool("kb_get_document", { document_id: documentId }));
    } catch {
      return null;
    }
  }, []);

  return {
    documents, stats, loading, error, query,
    search, ingest, remove, getDocument,
    refresh: () => { void refresh(); void refreshStats(); },
  };
}
