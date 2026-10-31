"""Documentation for knowledge base module."""

from factory.kb.mcp.docs_content import (
    CHROMADB_GUIDE,
    COLLECTIONS_GUIDE,
    GRAPH_RAG_GUIDE,
    KB_OVERVIEW,
    SEARCH_GUIDE,
)

DOCS = {
    "overview": KB_OVERVIEW,
    "chromadb": CHROMADB_GUIDE,
    "collections": COLLECTIONS_GUIDE,
    "search": SEARCH_GUIDE,
    "graph_rag": GRAPH_RAG_GUIDE,
}


def get_doc(name: str) -> str | None:
    """Get documentation by name."""
    return DOCS.get(name)


def list_docs() -> list[str]:
    """List available documentation."""
    return list(DOCS.keys())
