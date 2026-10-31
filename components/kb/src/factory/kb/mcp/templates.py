"""Prompt templates for knowledge base module."""

DOCUMENT_TEMPLATE = """
# Document: {doc_id}

## Metadata
Collection: {collection_id}
Created: {created_at}

## Content
{content}

## Tags
{tags}
"""

SEARCH_RESULT_TEMPLATE = """
# Search Results

## Query: {query}
Collection: {collection_id}
Results: {result_count}

## Matches
{matches}

## Context Envelope
{envelope}
"""

COLLECTION_TEMPLATE = """
# Collection: {collection_name}

## Configuration
ID: {collection_id}
Chunk Size: {chunk_size}
Chunk Overlap: {chunk_overlap}

## Statistics
Documents: {document_count}
Total Size: {total_size}

## Description
{description}
"""

INGEST_REPORT_TEMPLATE = """
# Ingestion Report

## Source
{source}

## Results
Documents Processed: {processed_count}
Documents Ingested: {ingested_count}
Errors: {error_count}

## Details
{details}
"""

TEMPLATES = {
    "document": DOCUMENT_TEMPLATE,
    "search-result": SEARCH_RESULT_TEMPLATE,
    "collection": COLLECTION_TEMPLATE,
    "ingest-report": INGEST_REPORT_TEMPLATE,
}


def get_template(name: str) -> str | None:
    """Get template by name."""
    return TEMPLATES.get(name)


def list_templates() -> list[str]:
    """List available templates."""
    return list(TEMPLATES.keys())


def render_template(name: str, **kwargs: str) -> str | None:
    """Render a template with provided values."""
    template = TEMPLATES.get(name)
    if template is None:
        return None
    try:
        return template.format(**kwargs)
    except KeyError:
        return template
