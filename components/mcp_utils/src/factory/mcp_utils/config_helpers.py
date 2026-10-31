"""Magnets-pattern config helpers.

Provides get_infra() and get_neo4j_config() that try the config brick
first (layered SSM + env resolution), falling back to plain env vars
when config brick is absent. This lets every brick work standalone
while snapping onto richer config when available.
"""

from __future__ import annotations

import os
from typing import Any


def get_infra(key: str, default: Any = None) -> Any:
    """Resolve infra config: config brick if available, else env var.

    Maps dotted key to env var: memory.backend -> MEMORY_BACKEND
    """
    try:
        from factory.config.interface import get_infra as _get_infra

        return _get_infra(key, default)
    except ImportError:
        return os.environ.get(key.upper().replace(".", "_"), default)


def get_neo4j_config() -> dict[str, str]:
    """Get Neo4j connection config: config brick if available, else env vars."""
    try:
        from factory.config.interface import get_neo4j_config as _get_neo4j_config

        return _get_neo4j_config()
    except ImportError:
        return {
            "uri": os.environ.get("NEO4J_URI", "bolt://localhost:7687"),
            "user": os.environ.get("NEO4J_USER", "neo4j"),
            "password": os.environ.get("NEO4J_PASSWORD", "password"),
            "database": os.environ.get("NEO4J_DATABASE", "neo4j"),
        }
