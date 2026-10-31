"""MCP prompts for knowledge base module."""

from __future__ import annotations

from typing import Any


def register(mcp: Any) -> None:
    """Register KB prompts."""

    @mcp.prompt()
    def kb_search_documents(
        query: str = "your search query",
        collection_id: str = "default",
    ) -> str:
        """Guide for searching documents in the knowledge base."""
        return f"""Help me search the knowledge base.

Query: {query}
Collection: {collection_id}

Please:
1. Execute the search using the search tool
2. Review the results and relevance scores
3. Summarize the key findings
4. Suggest follow-up queries if needed

Use the kb search tool with appropriate filters."""

    @mcp.prompt()
    def kb_ingest_document(
        collection_id: str = "default",
    ) -> str:
        """Guide for ingesting documents into the knowledge base."""
        return f"""Help me ingest a document into the knowledge base.

Target Collection: {collection_id}

Please guide me through:
1. Preparing the document content
2. Adding appropriate metadata
3. Using the ingest tool
4. Verifying the document was stored

Use the kb ingest tool."""

    @mcp.prompt()
    def kb_create_collection(
        collection_name: str = "my-collection",
    ) -> str:
        """Guide for creating a new collection."""
        return f"""Help me create a new KB collection.

Collection Name: {collection_name}

Please guide me through:
1. Choosing appropriate chunk size and overlap
2. Setting up the collection configuration
3. Creating the collection via authoring tools
4. Verifying the collection was created

Requires KB_ENABLE_AUTHORING_TOOLS=1."""

    @mcp.prompt()
    def kb_rag_workflow(
        question: str = "your question",
    ) -> str:
        """Guide for RAG (Retrieval Augmented Generation) workflow."""
        return f"""Help me answer a question using RAG.

Question: {question}

Please:
1. Search the KB for relevant context
2. Review the search results
3. Synthesize an answer using the retrieved context
4. Cite the source documents

Start with kb search, then formulate the answer."""

    @mcp.prompt()
    def kb_health_check() -> str:
        """Guide for checking KB health."""
        return """Help me check the health of the knowledge base.

Please:
1. Run health_check to get overall status
2. Check collection statistics
3. Verify ChromaDB connectivity
4. Report any issues found

Start with the health_check tool."""

    @mcp.prompt()
    def kb_bulk_ingest() -> str:
        """Guide for bulk document ingestion."""
        return """Help me bulk ingest documents into the KB.

Please guide me through:
1. Preparing documents for ingestion
2. Choosing the target collection
3. Setting up metadata schema
4. Executing batch ingestion
5. Verifying results

Consider chunking strategy and metadata consistency."""
