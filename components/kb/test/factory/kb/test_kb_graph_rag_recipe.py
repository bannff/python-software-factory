"""Recipe-driven tests for KB Graph-RAG entity extraction pipeline.

Mirrors `.agents/recipes/kb-graph-rag.md` steps:
init → ingest with extraction → ExtractionResult fields → shared entities →
orphan cleanup → per-call override → empty content → best-effort failure.

All mock-based — no real Neo4j or LLM required.
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

from factory.kb.runtime.models import Document, ExtractionResult
from factory.kb.runtime.retrieval.entity_extraction import EntityExtractor, _parse_extraction_json
from factory.kb.runtime.retrieval.neo4j_vector import Neo4jVectorConfig, Neo4jVectorStore

_EXT = "factory.kb.runtime.retrieval.entity_extraction.EntityExtractor"


class _FixedEmbedder:
    def embed(self, texts: list[str]) -> list[list[float]]:
        return [[0.1, 0.2, 0.3, 0.4] for _ in texts]

    @property
    def dimensions(self) -> int:
        return 4


def _session() -> MagicMock:
    s = MagicMock()
    s.run = MagicMock(return_value=[])
    s.__enter__ = lambda s: s
    s.__exit__ = MagicMock(return_value=False)
    return s


def _store(cfg: Neo4jVectorConfig | None = None) -> Neo4jVectorStore:
    driver = MagicMock()
    driver.session.return_value = _session()
    with patch("factory.kb.runtime.retrieval.neo4j_vector.GraphDatabase") as gd:
        gd.driver.return_value = driver
        store = Neo4jVectorStore(config=cfg or Neo4jVectorConfig(), embedder=_FixedEmbedder())
    store._driver = driver
    return store


def _doc(doc_id: str = "doc-001", content: str = "Some content") -> Document:
    return Document(id=doc_id, content=content, metadata={"source": "test"})


# -- Step 1: Init with entity extraction enabled ----------------------------

def test_init_config_extract_entities_enabled() -> None:
    assert Neo4jVectorConfig(extract_entities=True).extract_entities is True


def test_init_config_extract_entities_disabled() -> None:
    assert Neo4jVectorConfig(extract_entities=False).extract_entities is False


# -- Step 2: Ingest with entity extraction calls EntityExtractor ------------

def test_ingest_calls_entity_extractor() -> None:
    store = _store()
    fake = ExtractionResult(document_id="doc-001", entities_created=2, status="success")
    with patch(_EXT) as MockExt:
        MockExt.return_value.extract_and_store.return_value = fake
        result = store.add(_doc(), extract_entities=True)
    MockExt.return_value.extract_and_store.assert_called_once()
    assert result.status == "success"
    assert result.entities_created == 2


# -- Step 3: ExtractionResult has correct fields ----------------------------

def test_extraction_result_defaults() -> None:
    r = ExtractionResult(document_id="doc-001")
    assert (r.entities_created, r.relationships_created) == (0, 0)
    assert r.entity_types == []
    assert r.status == "success" and r.message == ""


def test_extraction_result_populated() -> None:
    r = ExtractionResult(
        document_id="doc-x", entities_created=5, relationships_created=3,
        entity_types=["Person", "Organization"], status="success",
        message="Extracted via neo4j-graphrag pipeline",
    )
    assert r.entities_created == 5
    assert r.entity_types == ["Person", "Organization"]


# -- Step 4: Shared entities across documents — MERGE semantics -------------

def test_shared_entities_use_merge() -> None:
    sess = _session()
    driver = MagicMock()
    driver.session.return_value = sess
    ext = EntityExtractor(driver=driver, database="neo4j")
    with patch("factory.kb.runtime.retrieval.entity_extraction.GRAPHRAG_AVAILABLE", False), \
         patch("factory.llm_gateway.interface.LLMRuntime") as MockLLM:
        resp = MagicMock()
        resp.content = '{"entities":[{"name":"Sam Altman","type":"Person"}],"relationships":[]}'
        MockLLM.return_value.get_provider.return_value.complete.return_value = resp
        ext.extract_and_store("doc-001", "Sam Altman founded OpenAI")
        ext.extract_and_store("doc-002", "Sam Altman spoke at a conference")
    merge_calls = [c for c in sess.run.call_args_list if "MERGE" in str(c)]
    assert len(merge_calls) >= 2, "MERGE should be called for each ingest"


# -- Step 5: Orphan cleanup on delete --------------------------------------

def test_delete_runs_orphan_cleanup() -> None:
    store = _store()
    rec = MagicMock()
    rec.__getitem__ = lambda _, k: 1
    store._driver.session.return_value = _session()
    store._driver.session.return_value.run.return_value = [rec]
    store.delete("doc-001")
    calls = [str(c) for c in store._driver.session.return_value.run.call_args_list]
    assert any("__Entity__" in c and "HAS_ENTITY" in c for c in calls)


# -- Step 6: Per-call extract_entities override (three-level precedence) ----

def test_per_call_extract_true_overrides_config_false() -> None:
    store = _store(Neo4jVectorConfig(extract_entities=False))
    with patch(_EXT) as M:
        M.return_value.extract_and_store.return_value = ExtractionResult(document_id="d")
        store.add(_doc(), extract_entities=True)
    M.return_value.extract_and_store.assert_called_once()


def test_per_call_extract_false_overrides_config_true() -> None:
    store = _store(Neo4jVectorConfig(extract_entities=True))
    with patch(_EXT) as M:
        store.add(_doc(), extract_entities=False)
    M.return_value.extract_and_store.assert_not_called()


def test_config_default_used_when_per_call_none() -> None:
    store = _store(Neo4jVectorConfig(extract_entities=True))
    with patch(_EXT) as M:
        M.return_value.extract_and_store.return_value = ExtractionResult(document_id="d")
        store.add(_doc())  # extract_entities not passed → None → config default
    M.return_value.extract_and_store.assert_called_once()


# -- Step 7: Empty content skipped -----------------------------------------

def test_empty_content_returns_skipped() -> None:
    result = EntityExtractor(driver=MagicMock()).extract_and_store("doc-001", "")
    assert result.status == "skipped" and result.document_id == "doc-001"


def test_whitespace_only_content_returns_skipped() -> None:
    result = EntityExtractor(driver=MagicMock()).extract_and_store("doc-002", "   \n\t  ")
    assert result.status == "skipped"


# -- Step 8: Extraction failure is best-effort -----------------------------

def test_extraction_failure_returns_failed_result() -> None:
    store = _store(Neo4jVectorConfig(extract_entities=True))
    with patch(_EXT) as M:
        M.return_value.extract_and_store.side_effect = RuntimeError("LLM down")
        result = store.add(_doc(), extract_entities=True)
    assert result.status == "failed"
    assert "LLM down" in result.message


# -- Bonus: _parse_extraction_json edge cases ------------------------------

def test_parse_extraction_json_valid() -> None:
    data = _parse_extraction_json('{"entities": [{"name": "X"}], "relationships": []}')
    assert len(data["entities"]) == 1


def test_parse_extraction_json_code_fenced() -> None:
    text = '```json\n{"entities": [], "relationships": []}\n```'
    assert _parse_extraction_json(text) == {"entities": [], "relationships": []}


def test_parse_extraction_json_garbage_returns_empty() -> None:
    assert _parse_extraction_json("not json at all") == {"entities": [], "relationships": []}
