"""KB search must report which backend answered, not null (issue #338)."""
from factory.kb.runtime.retrieval.bedrock import BedrockKBVectorStore
from factory.kb.runtime.retrieval.chroma import ChromaVectorStore
from factory.kb.runtime.retrieval.graph import KBGraphVectorStore
from factory.kb.runtime.retrieval.neo4j_vector import Neo4jVectorStore
from factory.kb.runtime.runtime import KBRuntime


def test_each_store_names_its_backend():
    assert Neo4jVectorStore.backend_name == "neo4j"
    assert KBGraphVectorStore.backend_name == "neo4j"
    assert ChromaVectorStore.backend_name == "chroma"
    assert BedrockKBVectorStore.backend_name == "bedrock"


def test_runtime_reports_backend_of_its_store(tmp_path):
    class Fake(ChromaVectorStore):
        def __init__(self) -> None:  # no client needed to read the name
            pass

    runtime = KBRuntime(tmp_path)
    assert runtime.backend_name is None
    runtime.set_vector_store(Fake())
    assert runtime.backend_name == "chroma"
