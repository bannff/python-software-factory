"""Neo4j vector store — HNSW semantic search with text fallback."""
from __future__ import annotations

import logging, os
from typing import Any

from pydantic import BaseModel, Field
from ..models import Document, SearchResult
from ..ports import VectorStore

try:
    from neo4j import GraphDatabase
    NEO4J_AVAILABLE = True
except ImportError:
    NEO4J_AVAILABLE = False
    GraphDatabase = None  # type: ignore[assignment, misc]

logger = logging.getLogger(__name__)


class Neo4jVectorConfig(BaseModel):
    """Configuration for Neo4j vector store."""
    uri: str = Field(default="bolt://localhost:7687")
    user: str = Field(default="neo4j")
    password: str = Field(default="password")
    database: str = Field(default="neo4j")
    index_name: str = Field(default="kb_documents")
    node_label: str = Field(default="KBDocument")
    embedding_property: str = Field(default="embedding")
    embedding_dimensions: int = Field(default=1024)
    embed_on_ingest: bool = Field(default=True)
    extract_entities: bool = Field(default=True)
    model_config = {"extra": "forbid"}


class Neo4jVectorStore(VectorStore):
    """Neo4j vector store with HNSW semantic search + text fallback."""

    def __init__(self, config: Neo4jVectorConfig | None = None, embedder: Any | None = None) -> None:
        if not NEO4J_AVAILABLE:
            raise ImportError("neo4j required: pip install neo4j")
        self._config = config or Neo4jVectorConfig(
            uri=os.environ.get("NEO4J_URI", "bolt://localhost:7687"),
            user=os.environ.get("NEO4J_USER", "neo4j"),
            password=os.environ.get("NEO4J_PASSWORD", "password"),
        )
        self._driver = GraphDatabase.driver(self._config.uri, auth=(self._config.user, self._config.password))
        self._embedder = embedder or self._default_embedder()
        self._ensure_index()

    def _default_embedder(self) -> Any:
        try:
            from .neo4j_embedding import LLMGatewayKBEmbedder
            return LLMGatewayKBEmbedder()
        except Exception:
            from .neo4j_embedding import NoOpKBEmbedder
            return NoOpKBEmbedder()

    def _ensure_index(self) -> None:
        cfg = self._config
        q = (f"CREATE VECTOR INDEX {cfg.index_name} IF NOT EXISTS FOR (n:{cfg.node_label}) "
             f"ON (n.{cfg.embedding_property}) OPTIONS {{indexConfig: "
             f"{{`vector.dimensions`: $dims, `vector.similarity_function`: 'cosine'}}}}")
        with self._driver.session(database=cfg.database) as s:
            try: s.run(q, dims=cfg.embedding_dimensions)
            except Exception: pass

    def _run(self, cypher: str, **params: Any) -> list[Any]:
        with self._driver.session(database=self._config.database) as s:
            return list(s.run(cypher, **params))

    def _set_embedding(self, doc_id: str, vector: list[float]) -> None:
        cfg = self._config
        self._run(f"MATCH (n:{cfg.node_label} {{id: $id}}) SET n.{cfg.embedding_property} = $vec",
                  id=doc_id, vec=vector)

    def _embed(self, texts: list[str]) -> list[float] | None:
        if self._embedder.dimensions == 0:
            return None
        vecs = self._embedder.embed(texts)
        return vecs[0] if vecs and vecs[0] else None

    def add(self, document: Document, extract_entities: bool | None = None) -> Any:
        cfg = self._config
        props: dict[str, Any] = {"id": document.id, "content": document.content, "source": document.source or ""}
        if document.metadata:
            for k, v in document.metadata.items():
                if isinstance(v, (str, int, float, bool)):
                    props[f"meta_{k}"] = v
        self._run(f"MERGE (n:{cfg.node_label} {{id: $id}}) SET n += $props", id=document.id, props=props)
        if cfg.embed_on_ingest:
            try:
                vec = self._embed([document.content])
                if vec:
                    self._set_embedding(document.id, vec)
            except Exception as e:
                logger.warning("Embedding failed for %s: %s", document.id, e)
        # Entity extraction — best-effort, never fails the ingest
        should_extract = extract_entities if extract_entities is not None else cfg.extract_entities
        if not should_extract:
            return None
        try:
            from .entity_extraction import EntityExtractor
            ext = EntityExtractor(driver=self._driver, database=cfg.database, node_label=cfg.node_label)
            result = ext.extract_and_store(document.id, document.content, document.metadata)
            logger.info("Entity extraction for %s: %s (%d entities, %d rels)",
                        document.id, result.status, result.entities_created, result.relationships_created)
            return result
        except Exception as e:
            logger.error("Entity extraction failed for %s: %s", document.id, e)
            from ..models import ExtractionResult
            return ExtractionResult(document_id=document.id, status="failed", message=str(e))

    def search(self, query: str, limit: int = 10, filters: dict[str, Any] | None = None,
               include_graph_context: bool = False) -> list[SearchResult]:
        try:
            vec = self._embed([query])
            if vec:
                results = self._vector_search(vec, limit)
                if results:
                    if include_graph_context:
                        self._enrich_graph_context(results)
                    return results
        except Exception as e:
            logger.warning("Vector search failed, falling back to text: %s", e)
        return self._text_search(query, limit)

    def delete(self, document_id: str) -> bool:
        cfg = self._config
        recs = self._run(
            f"MATCH (n:{cfg.node_label} {{id: $id}}) WITH n, count(n) AS c DETACH DELETE n RETURN c",
            id=document_id)
        deleted = bool(recs) and recs[0]["c"] > 0
        if deleted:
            self._run("MATCH (e:__Entity__) WHERE NOT (e)<-[:HAS_ENTITY]-() DELETE e")
        return deleted

    @staticmethod
    def _node_to_document(node_data: dict[str, Any], fallback_id: str = "") -> Document:
        meta = {k[5:]: v for k, v in node_data.items() if k.startswith("meta_")}
        return Document(id=node_data.get("id", fallback_id), content=node_data.get("content", ""),
                        metadata=meta, source=node_data.get("source"))

    def get(self, document_id: str) -> Document | None:
        recs = self._run(f"MATCH (n:{self._config.node_label} {{id: $id}}) RETURN n", id=document_id)
        return self._node_to_document(dict(recs[0]["n"]), fallback_id=document_id) if recs else None

    def list_documents(self, limit: int = 100) -> list[Document]:
        recs = self._run(f"MATCH (n:{self._config.node_label}) RETURN n ORDER BY n.id LIMIT $limit", limit=limit)
        return [self._node_to_document(dict(r["n"])) for r in recs]

    def _vector_search(self, query_vec: list[float], limit: int) -> list[SearchResult]:
        recs = self._run(
            "CALL db.index.vector.queryNodes($idx, $k, $vec) YIELD node, score "
            "RETURN node.id AS id, node.content AS content, score, node LIMIT $limit",
            idx=self._config.index_name, k=limit, vec=query_vec, limit=limit)
        return [self._to_result(r) for r in recs]

    def _text_search(self, query: str, limit: int) -> list[SearchResult]:
        recs = self._run(
            f"MATCH (n:{self._config.node_label}) WHERE n.content CONTAINS $q "
            f"RETURN n.id AS id, n.content AS content, 0.5 AS score, n AS node LIMIT $limit",
            q=query, limit=limit)
        return [self._to_result(r) for r in recs]

    @staticmethod
    def _to_result(record: Any) -> SearchResult:
        node = dict(record["node"]) if "node" in record.keys() else {}
        meta = {k[5:]: v for k, v in node.items() if k.startswith("meta_")}
        return SearchResult(document_id=record["id"], content=record["content"] or "",
                            score=float(record["score"]), metadata=meta)

    def _enrich_graph_context(self, results: list[SearchResult]) -> None:
        cypher = (f"MATCH (n:{self._config.node_label} {{id: $id}})-[r]-(m) "
                  "RETURN type(r) AS rt, labels(m) AS lb, m.id AS mid LIMIT 5")
        for res in results:
            try:
                ctx = [{"relationship": r["rt"], "labels": r["lb"], "id": r["mid"]}
                       for r in self._run(cypher, id=res.document_id)]
                if ctx:
                    res.metadata["graph_context"] = ctx
            except Exception:
                pass

    def backfill_embeddings(self, limit: int = 100) -> int:
        if self._embedder.dimensions == 0:
            return 0
        cfg = self._config
        recs = self._run(
            f"MATCH (n:{cfg.node_label}) WHERE n.{cfg.embedding_property} IS NULL "
            f"AND n.content IS NOT NULL RETURN n.id AS id, n.content AS content LIMIT $limit", limit=limit)
        count = 0
        for r in recs:
            try:
                if vec := self._embed([r["content"]]):
                    self._set_embedding(r["id"], vec)
                    count += 1
            except Exception as e:
                logger.warning("Backfill failed for %s: %s", r["id"], e)
        return count
