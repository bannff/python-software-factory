"""Storage runtime factory - selects and configures storage adapters.

Usage: ``StorageRuntime().get_blob_store("local")`` (or get_document_store /
get_sql_store / get_graph_store with their own backend names).
"""

from __future__ import annotations

import logging
from typing import Any

from .encrypted_store_cache import get_or_create_encrypted_store
from .ports import (BlobStore, DocumentStore, SQLStore, GraphStore, StorageHealth,
                    BusinessContentArtifactStore, CredentialSlotStore, OwnerSecretStore)

logger = logging.getLogger(__name__)


class StorageRuntime:
    """Factory for creating storage adapters."""

    def __init__(self, config: dict[str, Any] | None = None) -> None:
        from factory.mcp_utils.interface import get_infra
        self._config = config or {}
        self._blob_stores: dict[str, BlobStore] = {}
        self._document_stores: dict[str, DocumentStore] = {}
        self._sql_stores: dict[str, SQLStore] = {}
        self._graph_stores: dict[str, GraphStore] = {}
        self._protected_stores: dict[str, BusinessContentArtifactStore] = {}
        self._credential_slot_stores: dict[str, CredentialSlotStore] = {}
        self._owner_secret_stores: dict[str, OwnerSecretStore] = {}
        # Config-driven defaults (overridable per-call)
        self._default_doc = get_infra("storage.doc.backend", "tinydb")
        self._default_graph = get_infra("storage.graph.backend", "networkx")
        self._default_protected = self._config.get("protected_artifact_db_path", "./.storage/protected.db")

    def get_blob_store(
        self, backend: str = "local", **kwargs: Any
    ) -> BlobStore:
        """Get or create a blob store adapter."""
        cache_key = f"{backend}:{hash(frozenset(kwargs.items()))}"
        if cache_key not in self._blob_stores:
            self._blob_stores[cache_key] = self._create_blob_store(backend, **kwargs)
        return self._blob_stores[cache_key]

    def get_document_store(
        self, backend: str = "", **kwargs: Any
    ) -> DocumentStore:
        """Get or create a document store adapter."""
        backend = backend or self._default_doc
        cache_key = f"{backend}:{hash(frozenset(kwargs.items()))}"
        if cache_key not in self._document_stores:
            self._document_stores[cache_key] = self._create_document_store(backend, **kwargs)
        return self._document_stores[cache_key]

    def get_sql_store(
        self, backend: str = "sqlite", **kwargs: Any
    ) -> SQLStore:
        """Get or create a SQL store adapter."""
        cache_key = f"{backend}:{hash(frozenset(kwargs.items()))}"
        if cache_key not in self._sql_stores:
            self._sql_stores[cache_key] = self._create_sql_store(backend, **kwargs)
        return self._sql_stores[cache_key]

    def get_protected_artifact_store(self, db_path: str = "", **kwargs: Any) -> BusinessContentArtifactStore:
        """Return the only local protected-content data plane (never generic docs)."""
        from .adapters.protected_sqlite import SQLiteBusinessContentArtifactStore
        return get_or_create_encrypted_store(
            self._protected_stores, db_path, self._default_protected,
            SQLiteBusinessContentArtifactStore, **kwargs)

    def get_credential_slot_store(self, db_path: str = "", **kwargs: Any) -> CredentialSlotStore:
        """The mutable, encrypted, generation-fenced credential-slot store."""
        from .adapters.credential_slots_sqlite import SQLiteCredentialSlotStore
        default = self._config.get("credential_slot_db_path", "./.storage/credential-slots.db")
        return get_or_create_encrypted_store(
            self._credential_slot_stores, db_path, default,
            SQLiteCredentialSlotStore, **kwargs)

    def get_owner_secret_store(self, db_path: str = "", **kwargs: Any) -> OwnerSecretStore:
        """The mutable, encrypted, owner-named secret KV (no generation fence)."""
        from .adapters.owner_secrets_sqlite import SQLiteOwnerSecretStore
        default = self._config.get("owner_secret_db_path", "./.storage/owner-secrets.db")
        return get_or_create_encrypted_store(
            self._owner_secret_stores, db_path, default,
            SQLiteOwnerSecretStore, **kwargs)

    def get_graph_store(
        self, backend: str = "", **kwargs: Any
    ) -> GraphStore:
        """Get or create a graph store adapter."""
        backend = backend or self._default_graph
        cache_key = f"{backend}:{hash(frozenset(kwargs.items()))}"
        if cache_key not in self._graph_stores:
            self._graph_stores[cache_key] = self._create_graph_store(backend, **kwargs)
        return self._graph_stores[cache_key]

    def _create_blob_store(self, backend: str, **kwargs: Any) -> BlobStore:
        """Create a blob store adapter."""
        if backend == "local":
            from .adapters.blob_local import LocalBlobStore
            return LocalBlobStore(**kwargs)
        elif backend == "s3":
            from .adapters.blob_s3 import S3BlobStore
            return S3BlobStore(**kwargs)
        raise ValueError(f"Unknown blob backend: {backend}. Available: local, s3")

    def _create_document_store(self, backend: str, **kwargs: Any) -> DocumentStore:
        """Create a document store adapter."""
        if backend == "tinydb":
            from .adapters.doc_tinydb import TinyDBDocumentStore
            return TinyDBDocumentStore(**kwargs)
        elif backend == "sqlite":
            from .adapters.doc_sqlite import SQLiteDocumentStore
            return SQLiteDocumentStore(**kwargs)
        elif backend == "mongodb":
            from .adapters.doc_mongodb import MongoDBDocumentStore
            return MongoDBDocumentStore(**kwargs)
        elif backend == "neo4j":
            from factory.mcp_utils.interface import get_neo4j_config
            from .adapters.doc_neo4j import Neo4jDocumentStore
            neo4j = get_neo4j_config()
            neo4j_kwargs = {
                "uri": neo4j["uri"],
                "auth": (neo4j["user"], neo4j["password"]),
                **kwargs,
            }
            return Neo4jDocumentStore(**neo4j_kwargs)
        raise ValueError(f"Unknown document backend: {backend}. Available: sqlite, tinydb, mongodb, neo4j")

    def _create_sql_store(self, backend: str, **kwargs: Any) -> SQLStore:
        """Create a SQL store adapter."""
        if backend == "sqlite":
            from .adapters.sql_sqlite import SQLiteSQLStore
            return SQLiteSQLStore(**kwargs)
        elif backend == "postgres":
            from .adapters.sql_postgres import PostgresSQLStore
            return PostgresSQLStore(**kwargs)
        raise ValueError(f"Unknown SQL backend: {backend}. Available: sqlite, postgres")

    def _create_graph_store(self, backend: str, **kwargs: Any) -> GraphStore:
        """Create a graph store adapter."""
        if backend == "networkx":
            from .adapters.graph_networkx import NetworkXGraphStore
            return NetworkXGraphStore(**kwargs)
        elif backend == "neo4j":
            from factory.mcp_utils.interface import get_neo4j_config
            from .adapters.graph_neo4j import Neo4jGraphStore
            neo4j = get_neo4j_config()
            neo4j_kwargs = {
                "uri": neo4j["uri"],
                "auth": (neo4j["user"], neo4j["password"]),
                **kwargs,
            }
            return Neo4jGraphStore(**neo4j_kwargs)
        raise ValueError(f"Unknown graph backend: {backend}. Available: networkx, neo4j")

    def health_check(self) -> dict[str, StorageHealth]:
        """Check health of all active stores."""
        results = {}
        for name, store in self._blob_stores.items():
            results[f"blob:{name}"] = store.health_check()
        for name, store in self._document_stores.items():
            results[f"document:{name}"] = store.health_check()
        for name, store in self._sql_stores.items():
            results[f"sql:{name}"] = store.health_check()
        for name, store in self._graph_stores.items():
            results[f"graph:{name}"] = store.health_check()
        return results

    @staticmethod
    def available_backends() -> dict[str, list[str]]:
        """List available backends for each storage type."""
        return {
            "blob": ["local", "s3"],
            "document": ["sqlite", "tinydb", "mongodb", "neo4j"],
            "sql": ["sqlite", "postgres"],
            "graph": ["networkx", "neo4j"],
        }


# Global runtime instance
_runtime: StorageRuntime | None = None


def get_runtime() -> StorageRuntime:
    """Get the global storage runtime."""
    global _runtime
    if _runtime is None:
        _runtime = StorageRuntime()
    return _runtime


def reset_runtime() -> None:
    """Reset the global runtime (for testing)."""
    global _runtime
    _runtime = None
