"""BM25-based retriever using rank-bm25.

Replaces naive substring matching with proper TF-IDF-like ranking
via the BM25+ algorithm. Rebuilds the index on each query from the
vector store (suitable for small-to-medium corpora).

Uses BM25Plus over BM25Okapi because BM25+ guarantees non-negative
term scores regardless of corpus size (handles single-doc edge case).
"""
from __future__ import annotations

import math
from typing import Any

from rank_bm25 import BM25Plus

from factory.kb.runtime.models import SearchResult
from factory.kb.runtime.ports import Retriever, VectorStore


class BM25Retriever(Retriever):
    """BM25+-ranked retriever backed by rank-bm25."""

    def __init__(self, vector_store: VectorStore) -> None:
        self._vector_store = vector_store

    def retrieve(
        self, query: str, limit: int = 10, filters: dict[str, Any] | None = None,
    ) -> list[SearchResult]:
        docs = self._vector_store.list_documents(limit=10_000)
        if not docs:
            return []

        # Filter out documents with empty/whitespace-only content
        indexed_docs = [(i, doc) for i, doc in enumerate(docs) if doc.content.strip()]
        if not indexed_docs:
            return []

        corpus = [doc.content.lower().split() for _, doc in indexed_docs]
        bm25 = BM25Plus(corpus)
        tokenized_query = query.lower().split()
        scores = bm25.get_scores(tokenized_query)

        scored = sorted(
            zip([doc for _, doc in indexed_docs], scores),
            key=lambda x: x[1], reverse=True,
        )

        results: list[SearchResult] = []
        for doc, score in scored[:limit]:
            if score <= 0 or math.isnan(score):
                continue
            norm = min(score / (score + 1.0), 1.0)
            results.append(SearchResult(
                document_id=doc.id,
                content=doc.content[:500],
                score=round(norm, 4),
                metadata=doc.metadata,
            ))
        return results
