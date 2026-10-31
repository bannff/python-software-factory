"""MCP resources for knowledge base module."""

from __future__ import annotations

from typing import Any

from .docs import get_doc, list_docs
from .templates import get_template, list_templates


def register(mcp: Any, get_runtime: callable, get_config_dir: callable) -> None:
    """Register KB resources."""

    @mcp.resource("kb://docs")
    def kb_docs_list() -> str:
        """List available KB documentation."""
        docs = list_docs()
        lines = ["# Knowledge Base Documentation", ""]
        for doc in docs:
            lines.append(f"- kb://docs/{doc}")
        return "\n".join(lines)

    @mcp.resource("kb://docs/{name}")
    def kb_doc(name: str) -> str:
        """Get specific KB documentation."""
        doc = get_doc(name)
        if doc is None:
            return f"Documentation '{name}' not found. Available: {list_docs()}"
        return doc

    @mcp.resource("kb://templates")
    def kb_templates_list() -> str:
        """List available prompt templates."""
        templates = list_templates()
        lines = ["# KB Templates", ""]
        for t in templates:
            lines.append(f"- kb://templates/{t}")
        return "\n".join(lines)

    @mcp.resource("kb://templates/{name}")
    def kb_template(name: str) -> str:
        """Get specific prompt template."""
        template = get_template(name)
        if template is None:
            return f"Template '{name}' not found. Available: {list_templates()}"
        return template

    @mcp.resource("kb://collections")
    def kb_collections() -> str:
        """Get current collection registry."""
        runtime = get_runtime()
        registry = runtime.get_collection_registry()
        collections = registry.list_all()

        lines = ["# KB Collections", ""]
        if not collections:
            lines.append("No collections registered.")
            return "\n".join(lines)

        for c in collections:
            stats = runtime.get_collection_stats(c.id)
            lines.append(f"- {c.id}: {c.name} ({stats.document_count} docs)")

        return "\n".join(lines)

    @mcp.resource("kb://collections/{collection_id}")
    def kb_collection_detail(collection_id: str) -> str:
        """Get details for a specific collection."""
        runtime = get_runtime()
        registry = runtime.get_collection_registry()
        collection = registry.get(collection_id)

        if collection is None:
            return f"Collection '{collection_id}' not found."

        stats = runtime.get_collection_stats(collection_id)

        lines = [
            f"# Collection: {collection.name}",
            "",
            f"ID: {collection.id}",
            f"Documents: {stats.document_count}",
            f"Size: {stats.total_size_bytes} bytes",
        ]

        if collection.description:
            lines.extend(["", "## Description", collection.description])

        return "\n".join(lines)

    @mcp.resource("kb://config")
    def kb_config() -> str:
        """Get current KB configuration."""
        import os

        config_dir = get_config_dir()

        lines = [
            "# KB Configuration",
            "",
            f"Config Directory: {config_dir}",
            f"Chroma Directory: {os.environ.get('KB_CHROMA_DIR', './chroma_data')}",
            f"Authoring Enabled: {os.environ.get('KB_ENABLE_AUTHORING_TOOLS', '0') == '1'}",
        ]

        return "\n".join(lines)

    @mcp.resource("kb://factory-cross-ref")
    def kb_factory_cross_ref() -> str:
        """Cross-reference with other factory bricks."""
        return """# KB Factory Integration

## Related Bricks

### agent
- KB provides context for agent reasoning
- Agents can search and ingest documents

### workflow
- Workflow steps can query KB for context
- Document processing pipelines

### backend
- KB uses backend adapters for storage
- Graph adapter for knowledge relationships

### telemetry
- Track search latency and hit rates
- Monitor collection growth

## Integration Patterns

1. **RAG Pipeline**: Agent queries KB for context before LLM calls
2. **Document Processing**: Workflow ingests documents into KB
3. **Knowledge Graph**: Combine KB with graph adapter for relationships
"""
