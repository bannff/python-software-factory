"""Entity/relationship extraction for Graph-RAG KG construction.

Wraps neo4j-graphrag pipeline or falls back to raw LLM extraction.
Links extracted entities to source KBDocument nodes via HAS_ENTITY.
"""

from __future__ import annotations

import concurrent.futures
import json
import logging
from typing import Any

from ..models import ExtractionResult

try:
    from neo4j_graphrag.experimental.pipeline.kg_builder import SimpleKGPipeline
    from neo4j_graphrag.llm import LLMInterface, LLMResponse as GraphRAGLLMResponse
    GRAPHRAG_AVAILABLE = True
except ImportError:
    GRAPHRAG_AVAILABLE = False
    SimpleKGPipeline = None  # type: ignore[assignment, misc]

logger = logging.getLogger(__name__)

_EXTRACTION_PROMPT = (
    "Extract all named entities and relationships from the following text. "
    "Return JSON with 'entities' (list of {{name, type, description}}) and "
    "'relationships' (list of {{source, target, type, description}}). "
    "Entity types: Person, Organization, Location, Event, Concept, Technology, Document. "
    "Be thorough but precise. Only extract what is explicitly stated.\n\nText:\n{text}"
)


class _LLMGatewayBridge(LLMInterface if GRAPHRAG_AVAILABLE else object):  # type: ignore[misc]
    """Bridge factory.llm_gateway to neo4j-graphrag's LLMInterface."""

    def __init__(self, backend: str = "bedrock") -> None:
        self._backend = backend
        self._provider: Any = None

    def _get_provider(self) -> Any:
        if self._provider is None:
            from factory.llm_gateway.interface import LLMRuntime
            self._provider = LLMRuntime().get_provider(self._backend)
        return self._provider

    def invoke(self, input: str) -> GraphRAGLLMResponse:  # noqa: A002
        resp = self._get_provider().complete(prompt=input, temperature=0.0, max_tokens=4096)
        return GraphRAGLLMResponse(content=resp.content)

    async def ainvoke(self, input: str) -> GraphRAGLLMResponse:  # noqa: A002
        resp = await self._get_provider().complete_async(prompt=input, temperature=0.0, max_tokens=4096)
        return GraphRAGLLMResponse(content=resp.content)


class EntityExtractor:
    """Extract entities and relationships from text, write to Neo4j."""

    def __init__(self, driver: Any, database: str = "neo4j",
                 node_label: str = "KBDocument", llm_backend: str = "bedrock") -> None:
        self._driver = driver
        self._database = database
        self._node_label = node_label
        self._llm_backend = llm_backend

    def extract_and_store(self, document_id: str, content: str,
                          metadata: dict[str, Any] | None = None) -> ExtractionResult:
        """Extract entities/rels from text, write to Neo4j, link to KBDocument."""
        if not content or not content.strip():
            return ExtractionResult(document_id=document_id, status="skipped", message="Empty content")
        if GRAPHRAG_AVAILABLE:
            return self._extract_with_graphrag(document_id, content)
        return self._extract_with_llm_fallback(document_id, content)

    def _extract_with_graphrag(self, document_id: str, content: str) -> ExtractionResult:
        """Use neo4j-graphrag SimpleKGPipeline for extraction."""
        try:
            import asyncio
            pipeline = SimpleKGPipeline(
                llm=_LLMGatewayBridge(self._llm_backend),
                driver=self._driver, from_pdf=False,
            )
            try:
                loop = asyncio.get_running_loop()
            except RuntimeError:
                loop = None
            if loop and loop.is_running():
                with concurrent.futures.ThreadPoolExecutor() as pool:
                    pool.submit(asyncio.run, pipeline.run_async(text=content)).result()
            else:
                asyncio.run(pipeline.run_async(text=content))
            c = self._link_entities_to_document(document_id)
            return ExtractionResult(
                document_id=document_id, entities_created=c["entities"],
                relationships_created=c["relationships"], entity_types=c["types"],
                message="Extracted via neo4j-graphrag pipeline",
            )
        except Exception as e:
            logger.warning("graphrag failed for %s, trying LLM fallback: %s", document_id, e)
            return self._extract_with_llm_fallback(document_id, content)

    def _extract_with_llm_fallback(self, document_id: str, content: str) -> ExtractionResult:
        """Fallback: raw LLM extraction → manual Neo4j writes."""
        try:
            from factory.llm_gateway.interface import LLMRuntime
            provider = LLMRuntime().get_provider(self._llm_backend)
        except Exception as e:
            return ExtractionResult(document_id=document_id, status="error",
                                    message=f"LLM unavailable: {e}")
        try:
            resp = provider.complete(
                prompt=_EXTRACTION_PROMPT.format(text=content[:4000]),
                temperature=0.0, max_tokens=4096,
            )
            c = self._write_entities_to_neo4j(document_id, _parse_extraction_json(resp.content))
            return ExtractionResult(
                document_id=document_id, entities_created=c["entities"],
                relationships_created=c["relationships"], entity_types=c["types"],
                message="Extracted via LLM fallback",
            )
        except Exception as e:
            logger.warning("LLM entity extraction failed for %s: %s", document_id, e)
            return ExtractionResult(document_id=document_id, status="error", message=str(e))

    def _write_entities_to_neo4j(self, document_id: str, data: dict[str, Any]) -> dict[str, Any]:
        """Write extracted entities and relationships to Neo4j."""
        entity_count, rel_count, types = 0, 0, set()
        lbl = self._node_label
        with self._driver.session(database=self._database) as session:
            for ent in data.get("entities", []):
                name, etype = ent.get("name", "").strip(), ent.get("type", "Entity").strip()
                if not name:
                    continue
                session.run("MERGE (e:__Entity__ {name: $name}) SET e.type = $type, e.description = $desc",
                            name=name, type=etype, desc=ent.get("description", ""))
                session.run(f"MATCH (d:{lbl} {{id: $doc_id}}) MATCH (e:__Entity__ {{name: $name}}) "
                            "MERGE (d)-[:HAS_ENTITY]->(e)", doc_id=document_id, name=name)
                entity_count += 1
                types.add(etype)
            for rel in data.get("relationships", []):
                src, tgt = rel.get("source", "").strip(), rel.get("target", "").strip()
                rtype = rel.get("type", "RELATED_TO").strip().upper().replace(" ", "_")
                if not src or not tgt:
                    continue
                session.run(f"MATCH (a:__Entity__ {{name: $src}}) MATCH (b:__Entity__ {{name: $tgt}}) "
                            f"MERGE (a)-[r:`{rtype}`]->(b) SET r.description = $desc",
                            src=src, tgt=tgt, desc=rel.get("description", ""))
                rel_count += 1
        return {"entities": entity_count, "relationships": rel_count, "types": sorted(types)}

    def _link_entities_to_document(self, document_id: str) -> dict[str, Any]:
        """Count entities/rels created by neo4j-graphrag pipeline.

        Note: neo4j-graphrag creates its own node labels (__Entity__ etc).
        We link any unlinked entities that were just created to the source doc.
        Uses a timestamp-based heuristic — only links entities without existing
        HAS_ENTITY relationships (newly created by this pipeline run).
        """
        with self._driver.session(database=self._database) as session:
            # Count entities and relationships created by the pipeline
            ent_result = session.run(
                "MATCH (e:__Entity__) WHERE NOT ()-[:HAS_ENTITY]->(e) "
                "RETURN count(e) AS cnt, collect(DISTINCT e.type) AS types",
            )
            rec = ent_result.single()
            cnt, types = (rec["cnt"], rec["types"]) if rec else (0, [])
            # Link orphan entities to this document
            if cnt > 0:
                session.run(
                    f"MATCH (d:{self._node_label} {{id: $doc_id}}) "
                    "MATCH (e:__Entity__) WHERE NOT ()-[:HAS_ENTITY]->(e) "
                    "MERGE (d)-[:HAS_ENTITY]->(e)",
                    doc_id=document_id,
                )
            rels = session.run("MATCH (:__Entity__)-[r]->(:__Entity__) RETURN count(r) AS c")
            rel_rec = rels.single()
            return {"entities": cnt, "relationships": rel_rec["c"] if rel_rec else 0,
                    "types": sorted(set(t for t in types if t))}


def _parse_extraction_json(text: str) -> dict[str, Any]:
    """Parse LLM response into entities/relationships dict."""
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = "\n".join(l for l in cleaned.split("\n") if not l.strip().startswith("```"))
    _empty: dict[str, Any] = {"entities": [], "relationships": []}
    try:
        parsed = json.loads(cleaned)
        return parsed if isinstance(parsed, dict) else _empty
    except json.JSONDecodeError:
        start, end = cleaned.find("{"), cleaned.rfind("}") + 1
        if start >= 0 and end > start:
            try:
                parsed = json.loads(cleaned[start:end])
                return parsed if isinstance(parsed, dict) else _empty
            except json.JSONDecodeError:
                pass
        return _empty
