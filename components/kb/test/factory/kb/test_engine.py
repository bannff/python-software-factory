import pytest
from factory.kb.runtime.models import Document
from factory.kb.runtime.envelope import ContextEnvelope


def test_document_model():
    doc = Document(
        id="doc1",
        content="hello world",
        metadata={"source_id": "src1", "title": "Test Doc"},
    )
    assert doc.id == "doc1"
    assert doc.metadata["title"] == "Test Doc"


def test_envelope_validation():
    # Valid envelope
    env = ContextEnvelope(tenant_id="t1", attributes={"k1": "v1", "k2": 123})
    assert env.tenant_id == "t1"

    # Invalid envelope - too many attributes
    with pytest.raises(ValueError):
        ContextEnvelope(attributes={f"k{i}": "v" for i in range(51)})
