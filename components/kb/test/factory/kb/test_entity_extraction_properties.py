"""Property-based tests for entity extraction (Hypothesis).

Properties: JSON parsing (valid, markdown-wrapped, malformed, embedded),
empty content → skipped, LLM unavailable → error (Bug 3 regression),
write skips empty names/targets, types sorted, link counts correct.
"""

from __future__ import annotations

import json
from typing import Any
from unittest.mock import MagicMock, patch

from hypothesis import given, settings, strategies as st

from factory.kb.runtime.models import ExtractionResult
from factory.kb.runtime.retrieval.entity_extraction import (
    EntityExtractor,
    _parse_extraction_json,
)

# ---------------------------------------------------------------------------
# Strategies
# ---------------------------------------------------------------------------

_safe_id = st.text(
    min_size=1, max_size=20,
    alphabet=st.characters(whitelist_categories=("L", "N")),
)
_content = st.text(min_size=0, max_size=200)
_entity_name = st.text(min_size=0, max_size=30)
_entity_type = st.sampled_from(["Person", "Organization", "Location", "Event", "Concept"])

_entity = st.fixed_dictionaries({"name": _entity_name, "type": _entity_type,
                                 "description": st.text(min_size=0, max_size=50)})
_relationship = st.fixed_dictionaries({"source": _entity_name, "target": _entity_name,
                                       "type": st.sampled_from(["WORKS_AT", "LOCATED_IN", "RELATED_TO"]),
                                       "description": st.text(min_size=0, max_size=50)})
_extraction_data = st.fixed_dictionaries({"entities": st.lists(_entity, max_size=5),
                                          "relationships": st.lists(_relationship, max_size=5)})

# ---------------------------------------------------------------------------
# Mock helpers
# ---------------------------------------------------------------------------


def _make_extractor() -> tuple[EntityExtractor, MagicMock]:
    """Build an EntityExtractor with a mock Neo4j driver."""
    session = MagicMock()
    session.__enter__ = lambda s: s
    session.__exit__ = MagicMock(return_value=False)
    driver = MagicMock()
    driver.session.return_value = session
    return EntityExtractor(driver=driver), session


# ---------------------------------------------------------------------------
# Group 1: _parse_extraction_json
# ---------------------------------------------------------------------------


@settings(max_examples=50)
@given(data=_extraction_data)
def test_parse_valid_json_roundtrips(data: dict[str, Any]) -> None:
    """Valid JSON with entities/relationships parses correctly."""
    result = _parse_extraction_json(json.dumps(data))
    assert result["entities"] == data["entities"]
    assert result["relationships"] == data["relationships"]


@settings(max_examples=50)
@given(data=_extraction_data)
def test_parse_markdown_wrapped_json(data: dict[str, Any]) -> None:
    """Markdown-wrapped JSON (```json ... ```) is unwrapped and parsed."""
    wrapped = f"```json\n{json.dumps(data)}\n```"
    result = _parse_extraction_json(wrapped)
    assert result["entities"] == data["entities"]


@settings(max_examples=50)
@given(garbage=st.text(min_size=0, max_size=100).filter(lambda t: "{" not in t))
def test_parse_malformed_falls_back_to_empty(garbage: str) -> None:
    """Malformed JSON (no braces) falls back to empty entities/relationships."""
    result = _parse_extraction_json(garbage)
    assert result == {"entities": [], "relationships": []}


@settings(max_examples=50)
@given(data=_extraction_data,
       prefix=st.text(min_size=1, max_size=20).filter(lambda t: "{" not in t and "}" not in t))
def test_parse_json_embedded_in_text(data: dict[str, Any], prefix: str) -> None:
    """JSON embedded in surrounding text is extracted via first { to last }."""
    text = f"{prefix}{json.dumps(data)}trailing"
    result = _parse_extraction_json(text)
    assert result["entities"] == data["entities"]


# ---------------------------------------------------------------------------
# Group 2: extract_and_store routing
# ---------------------------------------------------------------------------


@settings(max_examples=50)
@given(doc_id=_safe_id, ws=st.sampled_from(["", "  ", "\t", "\n", "  \n  "]))
def test_empty_content_returns_skipped(doc_id: str, ws: str) -> None:
    """Empty or whitespace-only content returns status='skipped'."""
    ext, _ = _make_extractor()
    result = ext.extract_and_store(doc_id, ws)
    assert isinstance(result, ExtractionResult)
    assert result.status == "skipped"


# ---------------------------------------------------------------------------
# Group 3: LLM fallback error status (Bug 3 regression)
# ---------------------------------------------------------------------------


@settings(max_examples=50)
@given(doc_id=_safe_id, content=st.text(min_size=1, max_size=100).filter(lambda t: t.strip()))
def test_llm_unavailable_returns_error_not_skipped(doc_id: str, content: str) -> None:
    """When LLM import fails, fallback returns status='error', NOT 'skipped'."""
    ext, _ = _make_extractor()
    with patch(
        "factory.kb.runtime.retrieval.entity_extraction.GRAPHRAG_AVAILABLE", False,
    ), patch(
        "factory.kb.runtime.retrieval.entity_extraction.LLMRuntime",
        side_effect=ImportError("no llm"),
        create=True,
    ), patch.dict(
        "sys.modules", {"factory.llm_gateway.interface": None},
    ):
        result = ext.extract_and_store(doc_id, content)
    assert result.status == "error", f"Expected 'error' but got '{result.status}'"
    assert result.status != "skipped", "Bug 3 regression: must not be 'skipped'"


# ---------------------------------------------------------------------------
# Group 4: _write_entities_to_neo4j
# ---------------------------------------------------------------------------


@settings(max_examples=50)
@given(doc_id=_safe_id, data=_extraction_data)
def test_write_skips_empty_name_entities(doc_id: str, data: dict[str, Any]) -> None:
    """Entities with empty/whitespace names are skipped, others are written."""
    ext, session = _make_extractor()
    result = ext._write_entities_to_neo4j(doc_id, data)
    valid = [e for e in data["entities"] if e["name"].strip()]
    assert result["entities"] == len(valid)


@settings(max_examples=50)
@given(doc_id=_safe_id, data=_extraction_data)
def test_write_skips_empty_source_target_rels(doc_id: str, data: dict[str, Any]) -> None:
    """Relationships with empty source or target are skipped."""
    ext, session = _make_extractor()
    result = ext._write_entities_to_neo4j(doc_id, data)
    valid = [r for r in data["relationships"] if r["source"].strip() and r["target"].strip()]
    assert result["relationships"] == len(valid)


@settings(max_examples=50)
@given(doc_id=_safe_id, data=_extraction_data)
def test_write_entity_types_sorted(doc_id: str, data: dict[str, Any]) -> None:
    """Entity types are collected from valid entities and returned sorted."""
    ext, _ = _make_extractor()
    result = ext._write_entities_to_neo4j(doc_id, data)
    valid_types = sorted({e["type"].strip() for e in data["entities"] if e["name"].strip()})
    assert result["types"] == valid_types


# ---------------------------------------------------------------------------
# Group 5: _link_entities_to_document
# ---------------------------------------------------------------------------


@settings(max_examples=50)
@given(doc_id=_safe_id, ent_count=st.integers(min_value=0, max_value=20),
       rel_count=st.integers(min_value=0, max_value=20))
def test_link_returns_correct_counts(doc_id: str, ent_count: int, rel_count: int) -> None:
    """_link_entities_to_document returns entity and relationship counts from Neo4j."""
    ext, session = _make_extractor()
    types = ["Person", "Org"] if ent_count > 0 else []
    ent_rec = MagicMock()
    ent_rec.__getitem__ = lambda _, k: ent_count if k == "cnt" else types
    session.run.side_effect = [
        MagicMock(single=MagicMock(return_value=ent_rec)),                # entity query
        None,                                                              # MERGE link (if cnt > 0)
        MagicMock(single=MagicMock(return_value={"c": rel_count})),       # rel query
    ] if ent_count > 0 else [
        MagicMock(single=MagicMock(return_value=ent_rec)),
        MagicMock(single=MagicMock(return_value={"c": rel_count})),
    ]
    result = ext._link_entities_to_document(doc_id)
    assert result["entities"] == ent_count
    assert result["relationships"] == rel_count
