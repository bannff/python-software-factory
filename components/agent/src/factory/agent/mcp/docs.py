"""Documentation API for agent module."""

from .docs_content import (
    AGENT_OVERVIEW,
    LANG_RUNTIME_INTEGRATION,
    POLYMORPHIC_DESIGN,
    GRAPH_PATTERNS,
)
from .docs_events import EVENT_PROTOCOL

DOCS = {
    "overview": AGENT_OVERVIEW,
    "lang-runtime": LANG_RUNTIME_INTEGRATION,
    "polymorphic": POLYMORPHIC_DESIGN,
    "graph-patterns": GRAPH_PATTERNS,
    "event-protocol": EVENT_PROTOCOL,
}


def get_doc(name: str) -> str | None:
    """Get documentation by name."""
    return DOCS.get(name)


def list_docs() -> list[str]:
    """List available documentation."""
    return list(DOCS.keys())
